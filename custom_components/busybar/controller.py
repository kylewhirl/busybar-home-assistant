"""Interactive Home Assistant controller for BUSY Bar."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import Callable
from typing import Any

from busylib import AsyncBusyBar, exceptions
from homeassistant.const import ATTR_ENTITY_ID, STATE_CLOSED, STATE_OFF, STATE_ON
from homeassistant.core import Event, HomeAssistant, State, callback
from homeassistant.helpers.event import async_track_state_change_event

from .const import (
    APPLICATION_NAME,
    CONF_ACCENT_COLOR,
    CONF_DIAL_STEP,
    CONF_DISPLAY_PRIORITY,
    CONF_ENTITIES,
    DEFAULT_ACCENT_COLOR,
    DEFAULT_DIAL_STEP,
    DEFAULT_DISPLAY_PRIORITY,
    EVENT_INPUT,
)
from .dashboard import (
    NavigationState,
    apply_dial_delta,
    brightness_to_percent,
    build_dashboard_payload,
    build_message_payload,
    button_transition,
    parse_input_updates,
    percent_to_brightness,
)
from .icons import async_upload_icons
from .models import BusyBarConfigEntry

_LOGGER = logging.getLogger(__name__)


def _color_to_hex(value: Any) -> str:
    """Normalize an option value into a BUSY-compatible RGB color."""
    if isinstance(value, str) and value.startswith("#"):
        return value
    if isinstance(value, (list, tuple)) and len(value) >= 3:
        return "#{:02X}{:02X}{:02X}".format(*(int(channel) for channel in value[:3]))
    if isinstance(value, dict) and all(key in value for key in ("r", "g", "b")):
        return "#{r:02X}{g:02X}{b:02X}".format(**value)
    return DEFAULT_ACCENT_COLOR


def _friendly_name(state: State) -> str:
    return str(state.attributes.get("friendly_name") or state.entity_id.split(".", 1)[1])


def _level_for_state(state: State) -> int | None:
    """Return a common 0..100 level for supported adjustable entities."""
    domain = state.domain
    attrs = state.attributes
    if domain == "light":
        return brightness_to_percent(attrs.get("brightness")) if state.state == STATE_ON else 0
    if domain == "fan":
        return int(attrs.get("percentage") or 0)
    if domain == "cover":
        position = attrs.get("current_position")
        return int(position) if position is not None else None
    if domain == "media_player":
        volume = attrs.get("volume_level")
        return round(float(volume) * 100) if volume is not None else None
    if domain in ("number", "input_number"):
        try:
            minimum = float(attrs.get("min", 0))
            maximum = float(attrs.get("max", 100))
            value = float(state.state)
        except TypeError, ValueError:
            return None
        if maximum <= minimum:
            return None
        return round((value - minimum) * 100 / (maximum - minimum))
    return None


def _state_label(state: State) -> str:
    if state.domain == "climate" and state.attributes.get("temperature") is not None:
        return f"{state.attributes['temperature']}°"
    return state.state.replace("_", " ")


class BusyBarController:
    """Translate BUSY inputs into Home Assistant navigation and services."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: BusyBarConfigEntry,
        client: AsyncBusyBar,
    ) -> None:
        self.hass = hass
        self.entry = entry
        self.client = client
        self.navigation = NavigationState.INACTIVE
        self.selected_index = 0
        self.stream_connected = False
        self.switch_position: str | None = None
        self._listeners: set[Callable[[], None]] = set()
        self._stream_task: asyncio.Task[None] | None = None
        self._render_task: asyncio.Task[None] | None = None
        self._message_task: asyncio.Task[None] | None = None
        self._remove_state_listener: Callable[[], None] | None = None
        self._draw_lock = asyncio.Lock()

    @property
    def entities(self) -> list[str]:
        """Configured accessory entity IDs."""
        return list(self.entry.options.get(CONF_ENTITIES, []))

    @property
    def selected_entity_id(self) -> str | None:
        """Currently highlighted accessory."""
        entities = self.entities
        if not entities:
            return None
        self.selected_index %= len(entities)
        return entities[self.selected_index]

    @property
    def selected_name(self) -> str | None:
        """Friendly name of the highlighted accessory."""
        entity_id = self.selected_entity_id
        state = self.hass.states.get(entity_id) if entity_id else None
        return _friendly_name(state) if state else entity_id

    @property
    def active(self) -> bool:
        return self.navigation != NavigationState.INACTIVE

    def add_listener(self, listener: Callable[[], None]) -> Callable[[], None]:
        """Listen for runtime navigation and stream changes."""
        self._listeners.add(listener)

        def remove() -> None:
            self._listeners.discard(listener)

        return remove

    @callback
    def _notify(self) -> None:
        for listener in list(self._listeners):
            listener()

    async def async_start(self) -> None:
        """Start the WebSocket input stream and entity listener."""
        domains = {entity_id.split(".", 1)[0] for entity_id in self.entities}
        try:
            await async_upload_icons(
                self.client,
                domains,
                _color_to_hex(self.entry.options.get(CONF_ACCENT_COLOR, DEFAULT_ACCENT_COLOR)),
            )
        except exceptions.BusyBarError as err:
            _LOGGER.warning("Could not upload BUSY Bar dashboard icons: %s", err)
        if self.entities:
            self._remove_state_listener = async_track_state_change_event(
                self.hass, self.entities, self._async_state_changed
            )
        self._stream_task = self.hass.async_create_task(self._stream_loop(), "busybar input stream")

    async def async_stop(self) -> None:
        """Stop background work and remove this app's pixels."""
        if self._remove_state_listener:
            self._remove_state_listener()
            self._remove_state_listener = None
        for task in (self._stream_task, self._render_task, self._message_task):
            if task:
                task.cancel()
        tasks = [
            task for task in (self._stream_task, self._render_task, self._message_task) if task
        ]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        with contextlib.suppress(exceptions.BusyBarError):
            await self.client.display_clear(application_name=APPLICATION_NAME)

    async def _stream_loop(self) -> None:
        retry_delay = 1
        while True:
            try:
                async for message in self.client.stream_status_ws():
                    retry_delay = 1
                    if not self.stream_connected:
                        self.stream_connected = True
                        self._notify()
                    await self._async_handle_message(message)
            except asyncio.CancelledError:
                raise
            except exceptions.BusyBarError as err:
                if self.stream_connected:
                    self.stream_connected = False
                    self._notify()
                _LOGGER.warning("BUSY Bar input stream disconnected: %s", err)
            await asyncio.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, 30)

    async def _async_handle_message(self, message: dict[str, Any]) -> None:
        for event_type, value in parse_input_updates(message):
            self.hass.bus.async_fire(
                EVENT_INPUT,
                {
                    "config_entry_id": self.entry.entry_id,
                    "type": event_type,
                    "value": value,
                },
            )
            if event_type == "button":
                await self._async_handle_button(value)
            elif event_type == "encoder":
                await self._async_handle_encoder(value)
            elif event_type == "switch":
                self.switch_position = value
                self._notify()

    async def _async_handle_button(self, button: str) -> None:
        next_navigation, should_activate = button_transition(
            self.navigation, button, self.selected_entity_id is not None
        )
        if should_activate:
            await self._async_activate_selected()
            return
        if next_navigation == self.navigation:
            return
        if next_navigation == NavigationState.INACTIVE:
            await self.async_close()
        elif self.navigation == NavigationState.INACTIVE:
            await self.async_open()
        else:
            self.navigation = next_navigation
            self._notify()
            self.async_schedule_render()

    async def _async_handle_encoder(self, delta: int) -> None:
        if self.navigation == NavigationState.BROWSE:
            await self.async_select_relative(delta)
        elif self.navigation == NavigationState.CONTROL:
            await self._async_adjust_selected(delta)

    async def async_open(self) -> None:
        """Enter the accessory browser."""
        self.navigation = NavigationState.BROWSE
        self._notify()
        self.async_schedule_render()

    async def async_close(self) -> None:
        """Exit Home Assistant and clear its pixels."""
        self.navigation = NavigationState.INACTIVE
        self._notify()
        if self._render_task:
            self._render_task.cancel()
            self._render_task = None
        await self.client.display_clear(application_name=APPLICATION_NAME)

    async def async_select_relative(self, delta: int) -> None:
        """Move through configured accessories."""
        if not self.entities:
            return
        self.selected_index = (self.selected_index + delta) % len(self.entities)
        self._notify()
        self.async_schedule_render()

    @callback
    def _async_state_changed(self, event: Event) -> None:
        entity_id = event.data.get("entity_id")
        if self.active and entity_id == self.selected_entity_id:
            self.async_schedule_render()

    @callback
    def async_schedule_render(self) -> None:
        """Coalesce state bursts into one display update."""
        if not self.active or self._message_task:
            return
        if self._render_task and not self._render_task.done():
            self._render_task.cancel()
        self._render_task = self.hass.async_create_task(
            self._async_render_after_delay(), "busybar dashboard render"
        )

    async def _async_render_after_delay(self) -> None:
        await asyncio.sleep(0.08)
        await self.async_render()

    async def async_render(self) -> None:
        """Draw the current dashboard state on both displays."""
        entity_id = self.selected_entity_id
        state = self.hass.states.get(entity_id) if entity_id else None
        if state is None:
            await self.async_show_message("Choose accessories in BUSY Bar options", duration=2)
            return

        payload = build_dashboard_payload(
            domain=state.domain,
            name=_friendly_name(state),
            state_label=_state_label(state),
            navigation=self.navigation,
            accent_color=_color_to_hex(
                self.entry.options.get(CONF_ACCENT_COLOR, DEFAULT_ACCENT_COLOR)
            ),
            priority=int(self.entry.options.get(CONF_DISPLAY_PRIORITY, DEFAULT_DISPLAY_PRIORITY)),
            position=(self.selected_index + 1, len(self.entities)),
            level=_level_for_state(state),
        )
        async with self._draw_lock:
            await self.client.display_clear(application_name=APPLICATION_NAME)
            await self.client.display_draw(payload, sanitize_text=True)

    async def async_show_message(
        self, text: str, color: str | None = None, duration: float = 3
    ) -> None:
        """Temporarily replace the dashboard with a message."""
        current_task = asyncio.current_task()
        if self._message_task and self._message_task is not current_task:
            self._message_task.cancel()
        payload = build_message_payload(
            text,
            _color_to_hex(color)
            if color
            else _color_to_hex(self.entry.options.get(CONF_ACCENT_COLOR, DEFAULT_ACCENT_COLOR)),
            int(self.entry.options.get(CONF_DISPLAY_PRIORITY, DEFAULT_DISPLAY_PRIORITY)),
        )
        async with self._draw_lock:
            await self.client.display_clear(application_name=APPLICATION_NAME)
            await self.client.display_draw(payload, sanitize_text=True)

        async def restore() -> None:
            try:
                await asyncio.sleep(duration)
                if self.active:
                    await self.async_render()
                else:
                    await self.client.display_clear(application_name=APPLICATION_NAME)
            finally:
                self._message_task = None

        self._message_task = self.hass.async_create_task(restore(), "busybar message timeout")

    async def async_clear_display(self) -> None:
        """Clear only content owned by this integration."""
        await self.client.display_clear(application_name=APPLICATION_NAME)

    async def _async_activate_selected(self) -> None:
        entity_id = self.selected_entity_id
        state = self.hass.states.get(entity_id) if entity_id else None
        if state is None:
            return
        domain = state.domain
        service: str | None = None
        if domain in ("light", "switch", "fan", "input_boolean"):
            service = "toggle"
        elif domain == "media_player":
            service = "media_play_pause"
        elif domain == "cover":
            service = "open_cover" if state.state == STATE_CLOSED else "close_cover"
        elif domain == "lock":
            service = "unlock" if state.state == "locked" else "lock"
        elif domain in ("scene", "script"):
            service = "turn_on"
        elif domain == "button":
            service = "press"
        elif domain == "climate":
            service = "turn_on" if state.state == STATE_OFF else "turn_off"
        if service:
            await self.hass.services.async_call(
                domain, service, {ATTR_ENTITY_ID: entity_id}, blocking=False
            )

    async def _async_adjust_selected(self, delta: int) -> None:
        entity_id = self.selected_entity_id
        state = self.hass.states.get(entity_id) if entity_id else None
        if state is None:
            return
        domain = state.domain
        step = float(self.entry.options.get(CONF_DIAL_STEP, DEFAULT_DIAL_STEP))
        level = _level_for_state(state)
        data: dict[str, Any] = {ATTR_ENTITY_ID: entity_id}
        service: str | None = None

        if domain == "light":
            new_level = apply_dial_delta(level or 0, delta, step)
            service = "turn_off" if new_level == 0 else "turn_on"
            if new_level:
                data["brightness"] = percent_to_brightness(new_level)
        elif domain == "fan":
            service = "set_percentage"
            data["percentage"] = apply_dial_delta(level or 0, delta, step)
        elif domain == "cover":
            service = "set_cover_position"
            data["position"] = apply_dial_delta(level or 0, delta, step)
        elif domain == "media_player":
            service = "volume_set"
            data["volume_level"] = apply_dial_delta(level or 0, delta, step) / 100
        elif domain in ("number", "input_number"):
            minimum = float(state.attributes.get("min", 0))
            maximum = float(state.attributes.get("max", 100))
            new_level = apply_dial_delta(level or 0, delta, step)
            service = "set_value"
            data["value"] = minimum + (maximum - minimum) * new_level / 100
        elif domain == "climate":
            current = state.attributes.get("temperature")
            if current is not None:
                service = "set_temperature"
                data["temperature"] = float(current) + delta * 0.5

        if service:
            await self.hass.services.async_call(domain, service, data, blocking=False)
