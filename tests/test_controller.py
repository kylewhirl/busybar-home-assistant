"""Tests for Home Assistant accessory controls."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from busylib import exceptions, types
from homeassistant.core import State

from custom_components.busybar.const import CONF_DIAL_STEP, CONF_ENTITIES
from custom_components.busybar.controller import BusyBarController, _level_for_state
from custom_components.busybar.dashboard import NavigationState


class FakeStates:
    def __init__(self, state: State) -> None:
        self.state = state

    def get(self, entity_id: str) -> State | None:
        return self.state if entity_id == self.state.entity_id else None


def controller_for(state: State, *, dial_step: int = 5) -> tuple[BusyBarController, AsyncMock]:
    services = SimpleNamespace(async_call=AsyncMock())
    hass = SimpleNamespace(states=FakeStates(state), services=services)
    entry = SimpleNamespace(
        entry_id="test-entry",
        options={CONF_ENTITIES: [state.entity_id], CONF_DIAL_STEP: dial_step},
    )
    controller = BusyBarController(hass, entry, AsyncMock())
    return controller, services.async_call


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        (State("light.desk", "on", {"brightness": 128}), 50),
        (State("light.desk", "off", {"brightness": 255}), 0),
        (State("fan.office", "on", {"percentage": 35}), 35),
        (State("cover.blind", "open", {"current_position": 72}), 72),
        (State("media_player.speaker", "playing", {"volume_level": 0.42}), 42),
        (State("number.volume", "15", {"min": 10, "max": 30}), 25),
    ],
)
def test_level_for_adjustable_entities(state: State, expected: int) -> None:
    assert _level_for_state(state) == expected


@pytest.mark.parametrize(
    ("state", "service"),
    [
        (State("light.desk", "on"), "toggle"),
        (State("switch.outlet", "off"), "toggle"),
        (State("fan.office", "on"), "toggle"),
        (State("input_boolean.guest", "off"), "toggle"),
        (State("media_player.speaker", "playing"), "media_play_pause"),
        (State("cover.blind", "closed"), "open_cover"),
        (State("cover.blind", "open"), "close_cover"),
        (State("lock.front_door", "locked"), "unlock"),
        (State("lock.front_door", "unlocked"), "lock"),
        (State("scene.movie", "scening"), "turn_on"),
        (State("script.goodnight", "off"), "turn_on"),
        (State("button.restart", "unknown"), "press"),
        (State("climate.office", "off"), "turn_on"),
        (State("climate.office", "heat"), "turn_off"),
    ],
)
@pytest.mark.asyncio
async def test_start_button_maps_to_domain_service(state: State, service: str) -> None:
    controller, call = controller_for(state)

    await controller._async_activate_selected()

    call.assert_awaited_once_with(
        state.domain,
        service,
        {"entity_id": state.entity_id},
        blocking=False,
    )


@pytest.mark.parametrize(
    ("state", "delta", "domain", "service", "expected_data"),
    [
        (
            State("light.desk", "on", {"brightness": 128}),
            2,
            "light",
            "turn_on",
            {"entity_id": "light.desk", "brightness": 153},
        ),
        (
            State("light.desk", "on", {"brightness": 8}),
            -2,
            "light",
            "turn_off",
            {"entity_id": "light.desk"},
        ),
        (
            State("fan.office", "on", {"percentage": 35}),
            1,
            "fan",
            "set_percentage",
            {"entity_id": "fan.office", "percentage": 40},
        ),
        (
            State("cover.blind", "open", {"current_position": 72}),
            -2,
            "cover",
            "set_cover_position",
            {"entity_id": "cover.blind", "position": 62},
        ),
        (
            State("media_player.speaker", "playing", {"volume_level": 0.42}),
            2,
            "media_player",
            "volume_set",
            {"entity_id": "media_player.speaker", "volume_level": 0.52},
        ),
        (
            State("number.volume", "15", {"min": 10, "max": 30}),
            1,
            "number",
            "set_value",
            {"entity_id": "number.volume", "value": 16.0},
        ),
        (
            State("input_number.level", "50", {"min": 0, "max": 100}),
            -2,
            "input_number",
            "set_value",
            {"entity_id": "input_number.level", "value": 40.0},
        ),
        (
            State("climate.office", "heat", {"temperature": 70}),
            -2,
            "climate",
            "set_temperature",
            {"entity_id": "climate.office", "temperature": 69.0},
        ),
    ],
)
@pytest.mark.asyncio
async def test_dial_maps_to_domain_service(
    state: State,
    delta: int,
    domain: str,
    service: str,
    expected_data: dict[str, object],
) -> None:
    controller, call = controller_for(state)

    await controller._async_adjust_selected(delta)

    call.assert_awaited_once_with(domain, service, expected_data, blocking=False)


@pytest.mark.asyncio
async def test_browse_wraps_in_both_directions() -> None:
    state = State("light.one", "on")
    controller, _ = controller_for(state)
    controller.entry.options[CONF_ENTITIES] = ["light.one", "light.two", "light.three"]
    controller.async_schedule_render = lambda: None

    await controller.async_select_relative(-1)
    assert controller.selected_entity_id == "light.three"

    await controller.async_select_relative(1)
    assert controller.selected_entity_id == "light.one"


@pytest.mark.asyncio
async def test_empty_dashboard_draws_persistent_setup_hint() -> None:
    hass = SimpleNamespace(states=SimpleNamespace(get=lambda entity_id: None))
    entry = SimpleNamespace(entry_id="test-entry", options={CONF_ENTITIES: []})
    client = AsyncMock()
    controller = BusyBarController(hass, entry, client)

    await controller.async_render()

    client.display_clear.assert_not_awaited()
    client.display_draw.assert_awaited_once()
    payload = client.display_draw.await_args.args[0]
    assert any(
        element.text == "Choose accessories in BUSY Bar options"
        for element in payload.elements
        if hasattr(element, "text")
    )
    assert controller._message_task is None


@pytest.mark.asyncio
async def test_higher_priority_app_is_not_treated_as_a_controller_failure() -> None:
    state = State("light.one", "on", {"brightness": 128})
    controller, _ = controller_for(state)
    controller.client.display_draw.side_effect = exceptions.BusyBarAPIError(
        "Not drawn due to low priority", status_code=409
    )

    await controller.async_render()

    controller.client.display_clear.assert_not_awaited()
    controller.client.display_draw.assert_awaited_once()


@pytest.mark.asyncio
async def test_repeated_renders_keep_canvas_input_capture_active() -> None:
    """Updating pixels must not expose the underlying Apps UI between draws."""
    state = State("light.one", "on", {"brightness": 128})
    controller, _ = controller_for(state)
    controller.navigation = NavigationState.BROWSE

    await controller.async_render()
    await controller.async_render()

    controller.client.display_clear.assert_not_awaited()
    assert controller.client.display_draw.await_count == 2


@pytest.mark.asyncio
async def test_open_switches_physical_bar_to_apps_mode() -> None:
    state = State("light.one", "on", {"brightness": 128})
    controller, _ = controller_for(state)
    controller.async_schedule_render = lambda: None

    await controller.async_open()

    controller.client.input.assert_awaited_once_with(types.InputKey.APPS)
    controller.client.display_clear.assert_awaited_once_with()
    assert controller.navigation.value == "browse"


@pytest.mark.asyncio
async def test_physical_apps_position_opens_without_replaying_switch_input() -> None:
    state = State("light.one", "on", {"brightness": 128})
    controller, _ = controller_for(state)
    controller.async_schedule_render = lambda: None

    await controller._async_handle_switch("apps")

    assert controller.switch_position == "apps"
    assert controller.navigation.value == "browse"
    controller.client.input.assert_not_awaited()
    controller.client.display_clear.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_leaving_physical_apps_position_closes_dashboard() -> None:
    state = State("light.one", "on", {"brightness": 128})
    controller, _ = controller_for(state)
    controller.navigation = NavigationState.CONTROL

    await controller._async_handle_switch("busy")

    assert controller.switch_position == "busy"
    assert controller.navigation.value == "inactive"
    controller.client.display_clear.assert_awaited_once_with(
        application_name="home_assistant"
    )
