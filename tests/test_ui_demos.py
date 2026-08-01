"""Standalone UI studies stay deterministic without Home Assistant."""

from busylib import types

from demos.busybar_ui.layouts import render_demo
from demos.busybar_ui.models import (
    DemoView,
    HomeFlowDemo,
    parse_input_updates,
)


def test_select_opens_controls_directly_from_the_accessory_overview() -> None:
    demo = HomeFlowDemo()

    assert demo.view == DemoView.BROWSE
    demo.handle("button", "ok")
    assert demo.view == DemoView.PROPERTIES


def test_combined_control_screen_keeps_the_device_icon_and_all_controls_visible() -> None:
    demo = HomeFlowDemo()
    demo.handle("button", "ok")

    payload = render_demo(demo)
    front_images = [
        element
        for element in payload.elements
        if isinstance(element, types.ImageElement)
        and element.display == types.DisplayName.FRONT
        and element.path != "demo_blank.png"
    ]
    front_text = {
        element.text
        for element in payload.elements
        if isinstance(element, types.TextElement)
        and element.display == types.DisplayName.FRONT
        and element.text
    }

    assert front_images[0].path.endswith("_16.png")
    assert {"DIM", "RGB", "TEMP"}.issubset(front_text)


def test_dial_selects_an_accessory_then_a_control() -> None:
    demo = HomeFlowDemo()

    demo.handle("encoder", 1)
    assert demo.device.name == "Desk Lamp"
    demo.handle("button", "ok")
    demo.handle("encoder", 1)
    assert demo.property_name == "color"


def test_selected_control_is_edited_without_leaving_the_control_screen() -> None:
    demo = HomeFlowDemo()
    demo.handle("button", "ok")

    demo.handle("button", "ok")
    assert demo.view == DemoView.EDIT
    demo.handle("encoder", 2)
    assert demo.device.brightness == 90
    demo.handle("button", "ok")
    assert demo.view == DemoView.PROPERTIES


def test_start_toggles_the_selected_accessory_at_every_depth() -> None:
    demo = HomeFlowDemo()

    for expected_view in (
        DemoView.BROWSE,
        DemoView.PROPERTIES,
        DemoView.EDIT,
    ):
        assert demo.view == expected_view
        was_on = demo.device.on
        demo.handle("button", "start")
        assert demo.device.on is not was_on
        demo.handle("button", "ok")


def test_one_canvas_layout_survives_the_complete_navigation_stack() -> None:
    demo = HomeFlowDemo()
    payloads = []

    for _ in range(4):
        payloads.append(render_demo(demo))
        demo.handle("button", "ok")

    expected_slots = {
        (element.id, element.display): element.type for element in payloads[0].elements
    }
    for payload in payloads[1:]:
        assert {
            (element.id, element.display): element.type for element in payload.elements
        } == expected_slots


def test_demo_parser_accepts_physical_empty_select_event() -> None:
    message = {
        "updates": [
            {"input": {"button_event": {}}},
            {"input": {"encoder_event": {"delta": -1}}},
            {"input": {"button_event": {"button": "START"}}},
        ]
    }

    assert parse_input_updates(message) == [
        ("button", "ok"),
        ("encoder", -1),
        ("button", "start"),
    ]
