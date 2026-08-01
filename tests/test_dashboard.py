"""Tests for dashboard math, input parsing, and payloads."""

import pytest
from busylib import types

from custom_components.busybar.dashboard import (
    NavigationState,
    apply_dial_delta,
    brightness_to_percent,
    build_dashboard_payload,
    button_transition,
    parse_input_updates,
    percent_to_brightness,
)


@pytest.mark.parametrize(
    ("brightness", "percent"),
    [(0, 0), (128, 50), (255, 100), (None, 100)],
)
def test_brightness_to_percent(brightness: int | None, percent: int) -> None:
    assert brightness_to_percent(brightness) == percent


@pytest.mark.parametrize(("percent", "brightness"), [(0, 0), (50, 128), (100, 255), (150, 255)])
def test_percent_to_brightness(percent: int, brightness: int) -> None:
    assert percent_to_brightness(percent) == brightness


def test_dial_delta_clamps() -> None:
    assert apply_dial_delta(50, 2, 5) == 60
    assert apply_dial_delta(98, 1, 5) == 100
    assert apply_dial_delta(2, -1, 5) == 0


def test_parse_input_updates() -> None:
    message = {
        "updates": [
            {"input": {"button_event": {"button": "OK", "action": "PRESS"}}},
            {"input": {"encoder_event": {"delta": -2}}},
            {"input": {"switch_event": {"position": "APPS"}}},
            {"input": {"button_event": {"button": "START"}}},
            {"input": {"button_event": {}}},
            {"input": {"button_event": {"button": "START", "action": "RELEASE"}}},
        ]
    }

    assert parse_input_updates(message) == [
        ("button", "ok"),
        ("encoder", -2),
        ("switch", "apps"),
        ("button", "start"),
        ("button", "ok"),
    ]


def test_requested_navigation_flow() -> None:
    navigation, activate = button_transition(NavigationState.INACTIVE, "ok", True)
    assert (navigation, activate) == (NavigationState.BROWSE, False)

    navigation, activate = button_transition(navigation, "ok", True)
    assert (navigation, activate) == (NavigationState.CONTROL, False)

    navigation, activate = button_transition(navigation, "start", True)
    assert (navigation, activate) == (NavigationState.CONTROL, True)

    navigation, activate = button_transition(navigation, "back", True)
    assert (navigation, activate) == (NavigationState.BROWSE, False)

    navigation, activate = button_transition(navigation, "back", True)
    assert (navigation, activate) == (NavigationState.INACTIVE, False)


def test_start_toggles_highlighted_accessory_without_entering_control() -> None:
    navigation, activate = button_transition(NavigationState.BROWSE, "start", True)

    assert (navigation, activate) == (NavigationState.BROWSE, True)


@pytest.mark.parametrize("domain", ["light", "fan", "cover", "switch", "climate"])
def test_dashboard_payload_draws_both_displays(domain: str) -> None:
    payload = build_dashboard_payload(
        domain=domain,
        name="Desk Lamp",
        state_label="on",
        navigation=NavigationState.CONTROL,
        accent_color="#63E6BE",
        priority=50,
        position=(2, 5),
        level=72,
    )

    displays = {element.display for element in payload.elements}
    assert displays == {types.DisplayName.FRONT, types.DisplayName.BACK}
    assert payload.application_name == "home_assistant"
    assert len({element.id for element in payload.elements}) == len(payload.elements)


def test_level_bars_stay_on_screen() -> None:
    payload = build_dashboard_payload(
        domain="light",
        name="Kitchen",
        state_label="on",
        navigation=NavigationState.CONTROL,
        accent_color="#63E6BE",
        priority=50,
        position=(1, 1),
        level=100,
    )
    elements = {element.id: element for element in payload.elements}
    assert len(elements["front_level"].text) == 9
    assert len(elements["back_level"].text) == 24


def test_front_display_makes_control_mode_visible_and_scrolls_quickly() -> None:
    payload = build_dashboard_payload(
        domain="light",
        name="Studio Studio Light",
        state_label="on",
        navigation=NavigationState.BROWSE,
        accent_color="#63E6BE",
        priority=95,
        position=(1, 2),
        level=10,
    )
    elements = {element.id: element for element in payload.elements}

    assert elements["front_name"].scroll_rate >= 60
    assert elements["front_name"].scroll_start_delay <= 300
    assert elements["front_mode"].text == "SELECT"
