"""Interactive Home Assistant controller for BUSY Bar."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from collections.abc import Callable
from typing import Any

from busylib import AsyncBusyBar, exceptions, types
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
    ControlKind,
    NavigationState,
    apply_dial_delta,
    brightness_to_percent,
    build_dashboard_payload,
    build_message_payload,
    button_transition,
    clamp,
    controls_for,
    parse_input_updates,
    percent_to_brightness,
)
from .icons import async_icon_name_for_state, async_upload_icons, default_icon_name
from .models import BusyBarConfigEntry

_LOGGER = logging.getLogger(__name__)

RENDER_INTERVAL_SECONDS = 0.04
OPTIMISTIC_LEVEL_TTL_SECONDS = 2.0
LIGHT_COLOR_PRESETS: tuple[tuple[str, tuple[int, int, int]], ...] = (
    ("MINT", (99, 230, 190)),
    ("AMBER", (255, 191, 71)),
    ("BLUE", (80, 150, 255)),
    ("ROSE", (255, 94, 147)),
    ("LIME", (159, 232, 112)),
    ("VIOLET", (167, 139, 250)),
)


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


def _nearest_color_index(value: Any) -> int:
    """Return the nearest friendly preset to an RGB-like value."""
    if not isinstance(value, (list, tuple)) or len(value) < 3:
        return 0
    rgb = tuple(int(channel) for channel in value[:3])
    return min(
        range(len(LIGHT_COLOR_PRESETS)),
        key=lambda index: sum(
            (rgb[channel] - LIGHT_COLOR_PRESETS[index][1][channel]) ** 2
            for channel in range(3)
        ),
    )


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
        self.control_index = 0
        self.stream_connected = False
        self.switch_position: str | None = None
        self._listeners: set[Callable[[], None]] = set()
        self._stream_task: asyncio.Task[None] | None = None
        self._render_task: asyncio.Task[None] | None = None
        self._render_pending = False
        self._message_task: asyncio.Task[None] | None = None
        self._remove_state_listener: Callable[[], None] | None = None
        self._draw_lock = asyncio.Lock()
        self._optimistic_levels: dict[str, tuple[int, float]] = {}
        self._optimistic_controls: dict[
            tuple[str, ControlKind], tuple[int, float]
        ] = {}
        self._entity_icons: dict[str, str] = {}

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
    def selected_controls(self) -> tuple[ControlKind, ...]:
        """Controls available for the highlighted accessory."""
        entity_id = self.selected_entity_id
        state = self.hass.states.get(entity_id) if entity_id else None
        return controls_for(state.domain, state.attributes) if state else ()

    @property
    def selected_control(self) -> ControlKind | None:
        """Currently highlighted control on the combined device screen."""
        controls = self.selected_controls
        if not controls:
            return None
        self.control_index %= len(controls)
        return controls[self.control_index]

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
        icon_names: set[str] = set()
        for entity_id in self.entities:
            state = self.hass.states.get(entity_id)
            if state:
                icon_name = await async_icon_name_for_state(self.hass, state)
            else:
                icon_name = default_icon_name(entity_id.split(".", 1)[0])
            self._entity_icons[entity_id] = icon_name
            icon_names.add(icon_name)
        try:
            await async_upload_icons(
                self.client,
                icon_names,
                _color_to_hex(self.entry.options.get(CONF_ACCENT_COLOR, DEFAULT_ACCENT_COLOR)),
            )
        except exceptions.BusyBarError as err:
            _LOGGER.warning("Could not upload BUSY Bar dashboard icons: %s", err)
        if self.entities:
            self._remove_state_listener = async_track_state_change_event(
                self.hass, self.entities, self._async_state_changed
            )
        self._stream_task = self.entry.async_create_background_task(
            hass=self.hass,
            target=self._stream_loop(),
            name="busybar input stream",
        )

    async def async_stop(self) -> None:
        """Stop background work and remove this app's pixels."""
        self._render_pending = False
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
                await self._async_handle_switch(value)

    async def _async_handle_switch(self, position: str) -> None:
        """Follow the physical mode selector so built-in apps do not compete."""
        self.switch_position = position
        self._notify()
        if position == "apps":
            if not self.active:
                await self.async_open(request_apps_mode=False)
        elif self.active:
            await self.async_close()

    async def _async_handle_button(self, button: str) -> None:
        if (
            button == "ok"
            and self.navigation == NavigationState.CONTROL
            and not self.selected_controls
        ):
            return
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
            controls = self.selected_controls
            if controls:
                self.control_index = (self.control_index + delta) % len(controls)
                self._notify()
                self.async_schedule_render()
        elif self.navigation == NavigationState.EDIT:
            await self._async_adjust_selected(delta)

    async def async_open(self, *, request_apps_mode: bool = True) -> None:
        """Enter the accessory browser."""
        self.navigation = NavigationState.BROWSE
        self.control_index = 0
        self._notify()
        if request_apps_mode:
            try:
                await self.client.input(types.InputKey.APPS)
            except exceptions.BusyBarError as err:
                _LOGGER.warning("Could not switch BUSY Bar to Apps mode: %s", err)
        # Opening Home Assistant is an explicit takeover. A namespace-scoped
        # clear cannot displace an already-running app at equal priority.
        await self.client.display_clear()
        self.async_schedule_render()

    async def async_close(self) -> None:
        """Exit Home Assistant and clear its pixels."""
        self.navigation = NavigationState.INACTIVE
        self._notify()
        if self._render_task:
            self._render_task.cancel()
            self._render_task = None
        self._render_pending = False
        await self.client.display_clear(application_name=APPLICATION_NAME)

    async def async_select_relative(self, delta: int) -> None:
        """Move through configured accessories."""
        if not self.entities:
            return
        self.selected_index = (self.selected_index + delta) % len(self.entities)
        self.control_index = 0
        self._notify()
        self.async_schedule_render()

    def _display_level(self, state: State) -> int | None:
        """Return the latest dial value while HA catches up with the device."""
        optimistic = self._optimistic_levels.get(state.entity_id)
        if optimistic:
            level, expires_at = optimistic
            if time.monotonic() < expires_at:
                return level
            self._optimistic_levels.pop(state.entity_id, None)
        return _level_for_state(state)

    def _control_value(self, state: State, control: ControlKind | None) -> str:
        """Format the selected control's current value for the pixel display."""
        if control in (ControlKind.BRIGHTNESS, ControlKind.LEVEL):
            level = self._display_level(state)
            return f"{level}%" if level is not None else "--"
        if control == ControlKind.COLOR:
            optimistic = self._optimistic_control_value(state, control)
            color_index = (
                optimistic
                if optimistic is not None
                else _nearest_color_index(state.attributes.get("rgb_color"))
            )
            return LIGHT_COLOR_PRESETS[color_index][0]
        if control == ControlKind.TEMPERATURE:
            optimistic = self._optimistic_control_value(state, control)
            if state.domain == "light":
                value = (
                    optimistic
                    if optimistic is not None
                    else state.attributes.get("color_temp_kelvin")
                )
                return f"{int(value)}K" if value is not None else "--"
            value = state.attributes.get("temperature")
            return f"{value}°" if value is not None else "--"
        return _state_label(state).upper()

    def _optimistic_control_value(
        self, state: State, control: ControlKind
    ) -> int | None:
        """Return a recent dial value while Home Assistant catches up."""
        key = (state.entity_id, control)
        optimistic = self._optimistic_controls.get(key)
        if optimistic:
            value, expires_at = optimistic
            if time.monotonic() < expires_at:
                return value
            self._optimistic_controls.pop(key, None)
        return None

    def _browse_window(self) -> tuple[tuple[str, ...], int]:
        """Return the current four-accessory page and selected slot."""
        if not self.entities:
            return (), 0
        page_start = (self.selected_index // 4) * 4
        entity_ids = self.entities[page_start : page_start + 4]
        icon_names = []
        for entity_id in entity_ids:
            state = self.hass.states.get(entity_id)
            icon_names.append(
                self._entity_icons.get(
                    entity_id,
                    default_icon_name(
                        state.domain if state else entity_id.split(".", 1)[0]
                    ),
                )
            )
        return tuple(icon_names), self.selected_index - page_start

    @callback
    def _async_state_changed(self, event: Event) -> None:
        entity_id = event.data.get("entity_id")
        if self.active and entity_id == self.selected_entity_id:
            new_state = event.data.get("new_state")
            optimistic = self._optimistic_levels.get(entity_id)
            if optimistic and isinstance(new_state, State):
                if _level_for_state(new_state) == optimistic[0]:
                    self._optimistic_levels.pop(entity_id, None)
            if isinstance(new_state, State):
                color_key = (entity_id, ControlKind.COLOR)
                color = self._optimistic_controls.get(color_key)
                if color and _nearest_color_index(
                    new_state.attributes.get("rgb_color")
                ) == color[0]:
                    self._optimistic_controls.pop(color_key, None)
                temperature_key = (entity_id, ControlKind.TEMPERATURE)
                temperature = self._optimistic_controls.get(temperature_key)
                if temperature and int(
                    new_state.attributes.get("color_temp_kelvin") or 0
                ) == temperature[0]:
                    self._optimistic_controls.pop(temperature_key, None)
            self.async_schedule_render()

    @callback
    def async_schedule_render(self) -> None:
        """Coalesce state bursts into one display update."""
        if not self.active or self._message_task:
            return
        self._render_pending = True
        if self._render_task and not self._render_task.done():
            # Never restart the timer for every encoder tick. A fixed-rate
            # redraw loop will pick up the newest value after the active draw.
            return
        self._render_task = self.hass.async_create_task(
            self._async_render_after_delay(), "busybar dashboard render"
        )

    async def _async_render_after_delay(self) -> None:
        while self._render_pending and self.active and not self._message_task:
            self._render_pending = False
            await asyncio.sleep(RENDER_INTERVAL_SECONDS)
            await self.async_render()

    async def async_render(self) -> None:
        """Draw the current dashboard state on both displays."""
        entity_id = self.selected_entity_id
        state = self.hass.states.get(entity_id) if entity_id else None
        if state is None:
            payload = build_message_payload(
                "Choose accessories in BUSY Bar options",
                _color_to_hex(
                    self.entry.options.get(CONF_ACCENT_COLOR, DEFAULT_ACCENT_COLOR)
                ),
                int(
                    self.entry.options.get(
                        CONF_DISPLAY_PRIORITY, DEFAULT_DISPLAY_PRIORITY
                    )
                ),
            )
            await self._async_draw(payload)
            return

        level = self._display_level(state)
        state_label = _state_label(state)
        if state.domain == "light" and entity_id in self._optimistic_levels:
            state_label = STATE_OFF if level == 0 else STATE_ON

        controls = self.selected_controls
        selected_control = self.selected_control
        browse_icon_names, browse_selected = self._browse_window()
        icon_name = self._entity_icons.get(
            state.entity_id, default_icon_name(state.domain)
        )

        payload = build_dashboard_payload(
            domain=state.domain,
            name=_friendly_name(state),
            state_label=state_label,
            navigation=self.navigation,
            accent_color=_color_to_hex(
                self.entry.options.get(CONF_ACCENT_COLOR, DEFAULT_ACCENT_COLOR)
            ),
            priority=int(self.entry.options.get(CONF_DISPLAY_PRIORITY, DEFAULT_DISPLAY_PRIORITY)),
            position=(self.selected_index + 1, len(self.entities)),
            level=level,
            controls=controls,
            selected_control=selected_control,
            control_value=self._control_value(state, selected_control),
            browse_icon_names=browse_icon_names,
            browse_selected=browse_selected,
            icon_name=icon_name,
        )
        await self._async_draw(payload)

    async def _async_draw(self, payload: types.DisplayElements) -> bool:
        """Update the active Canvas app without releasing its input capture."""
        async with self._draw_lock:
            try:
                await self.client.display_draw(payload, sanitize_text=True)
            except exceptions.BusyBarAPIError as err:
                if err.status_code == 409:
                    _LOGGER.debug("Another BUSY app currently owns the display")
                    return False
                raise
        return True

    async def async_show_message(
        self, text: str, color: str | None = None, duration: float = 3
    ) -> None:
        """Temporarily replace the dashboard with a message."""
        current_task = asyncio.current_task()
        if self._message_task and self._message_task is not current_task:
            self._message_task.cancel()
            self._message_task = None
        payload = build_message_payload(
            text,
            _color_to_hex(color)
            if color
            else _color_to_hex(self.entry.options.get(CONF_ACCENT_COLOR, DEFAULT_ACCENT_COLOR)),
            int(self.entry.options.get(CONF_DISPLAY_PRIORITY, DEFAULT_DISPLAY_PRIORITY)),
        )
        if not await self._async_draw(payload):
            return

        async def restore() -> None:
            try:
                await asyncio.sleep(duration)
                if self.active:
                    await self.async_render()
                else:
                    await self.client.display_clear(application_name=APPLICATION_NAME)
            finally:
                if self._message_task is asyncio.current_task():
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
        level = self._display_level(state)
        data: dict[str, Any] = {ATTR_ENTITY_ID: entity_id}
        service: str | None = None
        new_level: int | None = None

        if domain == "light":
            if self.selected_control == ControlKind.COLOR:
                current_index = self._optimistic_control_value(
                    state, ControlKind.COLOR
                )
                if current_index is None:
                    current_index = _nearest_color_index(
                        state.attributes.get("rgb_color")
                    )
                color_index = (current_index + delta) % len(LIGHT_COLOR_PRESETS)
                service = "turn_on"
                data["rgb_color"] = LIGHT_COLOR_PRESETS[color_index][1]
                self._optimistic_controls[(entity_id, ControlKind.COLOR)] = (
                    color_index,
                    time.monotonic() + OPTIMISTIC_LEVEL_TTL_SECONDS,
                )
                self.async_schedule_render()
            elif self.selected_control == ControlKind.TEMPERATURE:
                minimum = int(state.attributes.get("min_color_temp_kelvin", 2200))
                maximum = int(state.attributes.get("max_color_temp_kelvin", 6500))
                optimistic = self._optimistic_control_value(
                    state, ControlKind.TEMPERATURE
                )
                current = int(
                    optimistic
                    if optimistic is not None
                    else state.attributes.get("color_temp_kelvin") or 3200
                )
                service = "turn_on"
                temperature = round(
                    clamp(current + delta * 200, minimum, maximum)
                )
                data["color_temp_kelvin"] = temperature
                self._optimistic_controls[(entity_id, ControlKind.TEMPERATURE)] = (
                    temperature,
                    time.monotonic() + OPTIMISTIC_LEVEL_TTL_SECONDS,
                )
                self.async_schedule_render()
            else:
                new_level = apply_dial_delta(level or 0, delta, step)
                service = "turn_off" if new_level == 0 else "turn_on"
                if new_level:
                    data["brightness"] = percent_to_brightness(new_level)
        elif domain == "fan":
            new_level = apply_dial_delta(level or 0, delta, step)
            service = "set_percentage"
            data["percentage"] = new_level
        elif domain == "cover":
            new_level = apply_dial_delta(level or 0, delta, step)
            service = "set_cover_position"
            data["position"] = new_level
        elif domain == "media_player":
            new_level = apply_dial_delta(level or 0, delta, step)
            service = "volume_set"
            data["volume_level"] = new_level / 100
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
            if new_level is not None:
                self._optimistic_levels[entity_id] = (
                    new_level,
                    time.monotonic() + OPTIMISTIC_LEVEL_TTL_SECONDS,
                )
                self.async_schedule_render()
            await self.hass.services.async_call(domain, service, data, blocking=False)
