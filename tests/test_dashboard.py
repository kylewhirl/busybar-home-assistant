"""Tests for dashboard math, input parsing, and payloads."""

import pytest
from busylib import types

from custom_components.busybar.dashboard import (
    ControlKind,
    NavigationState,
    apply_dial_delta,
    brightness_to_percent,
    build_dashboard_payload,
    button_transition,
    controls_for,
    icon_asset_path,
    parse_input_updates,
    percent_to_brightness,
)


def test_color_light_exposes_brightness_rgb_and_temperature_controls() -> None:
    assert controls_for(
        "light",
        {"supported_color_modes": ["hs", "color_temp"]},
    ) == (
        ControlKind.BRIGHTNESS,
        ControlKind.COLOR,
        ControlKind.TEMPERATURE,
    )


@pytest.mark.parametrize(
    ("domain", "expected"),
    [
        ("fan", (ControlKind.LEVEL,)),
        ("cover", (ControlKind.LEVEL,)),
        ("media_player", (ControlKind.LEVEL,)),
        ("number", (ControlKind.LEVEL,)),
        ("input_number", (ControlKind.LEVEL,)),
        ("climate", (ControlKind.TEMPERATURE,)),
        ("switch", ()),
    ],
)
def test_existing_accessory_types_keep_their_adjustable_control(
    domain: str, expected: tuple[ControlKind, ...]
) -> None:
    assert controls_for(domain, {}) == expected


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

    navigation, activate = button_transition(navigation, "ok", True)
    assert (navigation, activate) == (NavigationState.EDIT, False)

    navigation, activate = button_transition(navigation, "start", True)
    assert (navigation, activate) == (NavigationState.EDIT, True)

    navigation, activate = button_transition(navigation, "ok", True)
    assert (navigation, activate) == (NavigationState.CONTROL, False)

    navigation, activate = button_transition(navigation, "back", True)
    assert (navigation, activate) == (NavigationState.INACTIVE, False)


def test_back_exits_directly_from_control_because_firmware_closes_canvas() -> None:
    navigation, activate = button_transition(NavigationState.CONTROL, "back", True)

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


def test_light_control_screen_focuses_one_value_without_cramming_tabs() -> None:
    payload = build_dashboard_payload(
        domain="light",
        name="Desk Lamp",
        state_label="on",
        navigation=NavigationState.CONTROL,
        accent_color="#63E6BE",
        priority=100,
        position=(1, 4),
        level=72,
        controls=(
            ControlKind.BRIGHTNESS,
            ControlKind.COLOR,
            ControlKind.TEMPERATURE,
        ),
        selected_control=ControlKind.BRIGHTNESS,
        control_value="72%",
    )
    elements = {element.id: element for element in payload.elements}

    assert elements["front_image_0"].path == icon_asset_path(
        types.DisplayName.FRONT, "light", "active"
    )
    assert (elements["front_image_0"].x, elements["front_image_0"].y) == (1, 1)
    assert elements["front_text_0"].text == "BRIGHT"
    assert elements["front_text_1"].text == "72%"
    assert elements["front_text_2"].text == "1/3"
    assert elements["front_text_3"].text == ""


def test_browse_screen_shows_four_accessories_and_highlights_one() -> None:
    payload = build_dashboard_payload(
        domain="fan",
        name="Air Purifier",
        state_label="on",
        navigation=NavigationState.BROWSE,
        accent_color="#63E6BE",
        priority=100,
        position=(2, 4),
        level=35,
        browse_domains=("light", "fan", "light", "switch"),
        browse_selected=1,
    )
    elements = {element.id: element for element in payload.elements}

    assert elements["front_image_0"].path == icon_asset_path(
        types.DisplayName.FRONT, "light", "inactive"
    )
    assert elements["front_image_1"].path == icon_asset_path(
        types.DisplayName.FRONT, "fan", "active"
    )
    assert elements["front_image_2"].path == icon_asset_path(
        types.DisplayName.FRONT, "light", "inactive"
    )
    assert elements["front_image_3"].path == icon_asset_path(
        types.DisplayName.FRONT, "switch", "inactive"
    )
    assert [
        (elements[f"front_image_{index}"].x, elements[f"front_image_{index}"].y)
        for index in range(4)
    ] == [
        (2, 1),
        (20, 1),
        (38, 1),
        (56, 1),
    ]


def test_dashboard_uses_home_assistant_icons_without_changing_entity_domain() -> None:
    payload = build_dashboard_payload(
        domain="light",
        name="Desk Lamp",
        state_label="on",
        navigation=NavigationState.BROWSE,
        accent_color="#63E6BE",
        priority=100,
        position=(1, 4),
        browse_icon_names=(
            "mdi:desk-lamp",
            "mdi:floor-lamp",
            "mdi:fan",
            "mdi:power-plug",
        ),
        browse_selected=0,
        icon_name="mdi:desk-lamp",
    )
    elements = {element.id: element for element in payload.elements}

    assert elements["front_image_0"].path == icon_asset_path(
        types.DisplayName.FRONT, "mdi:desk-lamp", "active"
    )
    assert elements["front_image_1"].path == icon_asset_path(
        types.DisplayName.FRONT, "mdi:floor-lamp", "inactive"
    )
    assert elements["front_image_2"].path == icon_asset_path(
        types.DisplayName.FRONT, "mdi:fan", "inactive"
    )
    assert elements["front_image_3"].path == icon_asset_path(
        types.DisplayName.FRONT, "mdi:power-plug", "inactive"
    )
    assert elements["back_state"].text.startswith("LIGHT")


def test_nonadjustable_accessory_still_gets_combined_power_screen() -> None:
    payload = build_dashboard_payload(
        domain="switch",
        name="Outlet",
        state_label="off",
        navigation=NavigationState.CONTROL,
        accent_color="#63E6BE",
        priority=100,
        position=(1, 1),
        control_value="OFF",
    )
    elements = {element.id: element for element in payload.elements}

    assert elements["front_image_0"].path == icon_asset_path(
        types.DisplayName.FRONT, "switch", "inactive"
    )
    assert elements["front_text_0"].text == "POWER"
    assert elements["front_text_1"].text == "OFF"
    assert elements["front_text_2"].text == ""


def test_level_value_stays_on_combined_control_screen() -> None:
    payload = build_dashboard_payload(
        domain="light",
        name="Kitchen",
        state_label="on",
        navigation=NavigationState.CONTROL,
        accent_color="#63E6BE",
        priority=50,
        position=(1, 1),
        level=100,
        controls=(ControlKind.BRIGHTNESS,),
        selected_control=ControlKind.BRIGHTNESS,
        control_value="100%",
    )
    elements = {element.id: element for element in payload.elements}
    assert elements["front_text_1"].text == "100%"
    assert elements["back_state"].text == "DIM  ·  100%"


def test_editing_state_is_visible_without_competing_with_the_value() -> None:
    payload = build_dashboard_payload(
        domain="light",
        name="Kitchen",
        state_label="on",
        navigation=NavigationState.EDIT,
        accent_color="#63E6BE",
        priority=100,
        position=(1, 3),
        controls=(ControlKind.BRIGHTNESS, ControlKind.COLOR, ControlKind.TEMPERATURE),
        selected_control=ControlKind.COLOR,
        control_value="MINT",
    )
    elements = {element.id: element for element in payload.elements}

    assert elements["front_text_0"].text == "COLOR"
    assert elements["front_text_1"].text == "MINT"
    assert elements["front_text_2"].text == "2/3"
    assert elements["front_text_3"].text == "EDIT"


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


def test_control_hint_uses_select_to_edit_selected_property() -> None:
    payload = build_dashboard_payload(
        domain="light",
        name="Desk Lamp",
        state_label="on",
        navigation=NavigationState.CONTROL,
        accent_color="#63E6BE",
        priority=95,
        position=(1, 2),
        level=50,
    )
    elements = {element.id: element for element in payload.elements}

    assert "SELECT: EDIT" in elements["back_hint"].text
