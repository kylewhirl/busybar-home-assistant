"""Standalone UI studies stay deterministic without Home Assistant."""

from busylib import types

from demos.busybar_ui.layouts import render_demo
from demos.busybar_ui.models import (
    CapabilitiesDemo,
    DemoView,
    FocusDemo,
    GridDemo,
    parse_input_updates,
)


def test_grid_flow_browses_selects_toggles_and_dims() -> None:
    demo = GridDemo()

    demo.handle("encoder", 1)
    assert demo.selected == 1
    demo.handle("button", "ok")
    assert demo.view == DemoView.CONTROL
    demo.handle("encoder", 2)
    assert demo.device.brightness == 55
    demo.handle("button", "start")
    assert demo.device.on is False
    demo.handle("button", "ok")
    assert demo.view == DemoView.BROWSE


def test_capability_flow_selects_and_edits_each_property() -> None:
    demo = CapabilitiesDemo()
    demo.handle("button", "ok")
    assert demo.view == DemoView.PROPERTIES

    demo.handle("encoder", 1)
    assert demo.property_name == "color"
    demo.handle("button", "ok")
    demo.handle("encoder", 2)
    assert demo.device.color_label == "BLUE"
    demo.handle("button", "ok")

    demo.handle("encoder", 1)
    assert demo.property_name == "temperature"
    demo.handle("button", "ok")
    demo.handle("encoder", 2)
    assert demo.device.kelvin == 3400


def test_focus_carousel_wraps_and_uses_large_back_icon() -> None:
    demo = FocusDemo()
    demo.handle("encoder", -1)
    assert demo.selected == len(demo.devices) - 1

    payload = render_demo(demo)
    back_icons = [
        element
        for element in payload.elements
        if isinstance(element, types.ImageElement)
        and element.display == types.DisplayName.BACK
    ]
    assert back_icons[0].path.endswith("_56.png")


def test_every_view_keeps_the_same_canvas_slot_ids_and_element_types() -> None:
    for demo in (GridDemo(), CapabilitiesDemo(), FocusDemo()):
        first = render_demo(demo)
        demo.handle("button", "ok")
        second = render_demo(demo)
        first_slots = {(element.id, element.display): element.type for element in first.elements}
        second_slots = {(element.id, element.display): element.type for element in second.elements}
        assert first_slots == second_slots


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
