"""Three fixed-slot BUSY Canvas layouts for fast physical comparison."""

from __future__ import annotations

from dataclasses import dataclass

from busylib import types

from .icons import APPLICATION_NAME, asset_path
from .models import BaseDemo, CapabilitiesDemo, DemoView, FocusDemo, GridDemo

ACCENT = "#63E6BE"
MUTED = "#777777FF"
WHITE = "#FFFFFFFF"
DIM = "#A0A0A0FF"
PRIORITY = 100


@dataclass(frozen=True)
class ImageSlot:
    x: int = 0
    y: int = 0
    kind: str | None = None
    size: int = 16


@dataclass(frozen=True)
class TextSlot:
    x: int = 0
    y: int = 0
    text: str = ""
    font: str = "tiny"
    color: str = WHITE
    align: str | None = None
    width: int | None = None


def _payload(
    *,
    front_images: list[ImageSlot],
    back_images: list[ImageSlot],
    front_text: list[TextSlot],
    back_text: list[TextSlot],
) -> types.DisplayElements:
    """Fill stable slots so view changes never tear down BUSY Canvas."""
    elements: list[types.DisplayElement] = []
    for display, prefix, slots, count in (
        (types.DisplayName.FRONT, "fi", front_images, 2),
        (types.DisplayName.BACK, "bi", back_images, 4),
    ):
        padded = slots + [ImageSlot()] * (count - len(slots))
        for index, slot in enumerate(padded[:count]):
            path = asset_path(slot.kind, slot.size) if slot.kind else "demo_blank.png"
            elements.append(
                types.ImageElement(
                    id=f"{prefix}{index}", display=display, x=slot.x, y=slot.y, path=path
                )
            )
    for display, prefix, slots, count in (
        (types.DisplayName.FRONT, "ft", front_text, 4),
        (types.DisplayName.BACK, "bt", back_text, 12),
    ):
        padded = slots + [TextSlot()] * (count - len(slots))
        for index, slot in enumerate(padded[:count]):
            extra: dict[str, object] = {}
            if slot.align:
                extra["align"] = slot.align
            if slot.width:
                extra.update(
                    width=slot.width,
                    scroll_rate=70,
                    scroll_start_delay=150,
                    scroll_repeat_delay=250,
                )
            elements.append(
                types.TextElement(
                    id=f"{prefix}{index}",
                    display=display,
                    x=slot.x,
                    y=slot.y,
                    text=slot.text,
                    font=slot.font,
                    color=slot.color,
                    **extra,
                )
            )
    return types.DisplayElements(
        application_name=APPLICATION_NAME,
        priority=PRIORITY,
        elements=elements,
    )


def _front(demo: BaseDemo, mode: str) -> tuple[list[ImageSlot], list[TextSlot]]:
    device = demo.device
    return (
        [ImageSlot(1, 1, device.kind, 14)],
        [
            TextSlot(17, 0, device.name, "tiny", ACCENT if device.on else MUTED, width=42),
            TextSlot(17, 8, device.state_label, "small", WHITE),
            TextSlot(71, 8, mode, "tiny", ACCENT, "top_right"),
        ],
    )


def _level_bar(level: int, width: int = 18) -> str:
    filled = round(width * level / 100)
    return "=" * filled + "-" * (width - filled)


def _grid(demo: GridDemo) -> types.DisplayElements:
    front_images, front_text = _front(
        demo, "LIST" if demo.view == DemoView.BROWSE else "DIM"
    )
    if demo.view == DemoView.BROWSE:
        images = [
            ImageSlot(3, 11 + index * 15, device.kind, 14)
            for index, device in enumerate(demo.devices)
        ]
        text = [TextSlot(3, 1, f"DEVICES  {demo.selected + 1}/{len(demo.devices)}", "tiny", MUTED)]
        for index, device in enumerate(demo.devices):
            selected = index == demo.selected
            text.append(
                TextSlot(
                    20,
                    12 + index * 15,
                    f"> {device.name}" if selected else f"  {device.name}",
                    "small",
                    ACCENT if selected else WHITE,
                    width=91,
                )
            )
            text.append(
                TextSlot(
                    156,
                    12 + index * 15,
                    device.state_label,
                    "tiny",
                    ACCENT if device.on else MUTED,
                    "top_right",
                )
            )
        text.append(TextSlot(3, 72, "DIAL MOVE  OK OPEN  START POWER", "tiny", MUTED))
        return _payload(
            front_images=front_images,
            back_images=images,
            front_text=front_text,
            back_text=text,
        )

    device = demo.device
    return _payload(
        front_images=front_images,
        back_images=[ImageSlot(4, 13, device.kind, 56)],
        front_text=front_text,
        back_text=[
            TextSlot(4, 2, f"DEVICE {demo.selected + 1}/{len(demo.devices)}", "tiny", MUTED),
            TextSlot(66, 14, device.name, "normal", WHITE, width=88),
            TextSlot(66, 37, device.state_label, "bold", ACCENT if device.on else MUTED),
            TextSlot(66, 54, _level_bar(device.brightness), "tiny", WHITE),
            TextSlot(4, 72, "DIAL DIM  START POWER  OK LIST", "tiny", MUTED),
        ],
    )


def _property_value(demo: CapabilitiesDemo, name: str) -> str:
    if name == "brightness":
        return f"{demo.device.brightness}%"
    if name == "color":
        return demo.device.color_label
    return f"{demo.device.kelvin}K"


def _capabilities(demo: CapabilitiesDemo) -> types.DisplayElements:
    mode = {
        DemoView.BROWSE: "OPEN",
        DemoView.PROPERTIES: "PICK",
        DemoView.EDIT: "EDIT",
    }[demo.view]
    front_images, front_text = _front(demo, mode)
    device = demo.device
    if demo.view == DemoView.BROWSE:
        return _payload(
            front_images=front_images,
            back_images=[ImageSlot(5, 12, device.kind, 56)],
            front_text=front_text,
            back_text=[
                TextSlot(68, 13, device.name, "normal", WHITE, width=86),
                TextSlot(68, 36, device.state_label, "bold", ACCENT if device.on else MUTED),
                TextSlot(68, 54, "3 CONTROLS", "small", DIM),
                TextSlot(5, 72, "DIAL DEVICE  OK CONTROLS  START POWER", "tiny", MUTED),
            ],
        )
    if demo.view == DemoView.PROPERTIES:
        text = [
            TextSlot(42, 2, device.name, "small", WHITE, width=112),
            TextSlot(4, 72, "DIAL PICK  OK EDIT  START POWER", "tiny", MUTED),
        ]
        for index, name in enumerate(demo.properties):
            selected = index == demo.property_index
            text.extend(
                [
                    TextSlot(
                        42,
                        20 + index * 16,
                        f"> {name.upper()}" if selected else f"  {name.upper()}",
                        "small",
                        ACCENT if selected else WHITE,
                    ),
                    TextSlot(
                        154,
                        20 + index * 16,
                        _property_value(demo, name),
                        "small",
                        ACCENT if selected else DIM,
                        "top_right",
                    ),
                ]
            )
        return _payload(
            front_images=front_images,
            back_images=[ImageSlot(4, 18, device.kind, 32)],
            front_text=front_text,
            back_text=text,
        )

    property_name = demo.property_name
    value = _property_value(demo, property_name)
    return _payload(
        front_images=front_images,
        back_images=[ImageSlot(5, 17, device.kind, 32)],
        front_text=[
            front_text[0],
            TextSlot(17, 8, f"{property_name[:4].upper()} {value}", "small", WHITE),
            front_text[2],
        ],
        back_text=[
            TextSlot(42, 10, property_name.upper(), "small", MUTED),
            TextSlot(42, 27, value, "large", ACCENT),
            TextSlot(
                42,
                55,
                _level_bar(device.brightness)
                if property_name == "brightness"
                else device.color_label if property_name == "color" else "COOL <-----> WARM",
                "tiny",
                WHITE,
            ),
            TextSlot(5, 72, "DIAL CHANGE  OK DONE  START POWER", "tiny", MUTED),
        ],
    )


def _focus(demo: FocusDemo) -> types.DisplayElements:
    front_images, front_text = _front(
        demo, "FOCUS" if demo.view == DemoView.BROWSE else "DIM"
    )
    device = demo.device
    position = "  ".join(
        "[o]" if index == demo.selected else " o " for index in range(len(demo.devices))
    )
    hint = (
        "DIAL NEXT  OK DIM  START POWER"
        if demo.view == DemoView.BROWSE
        else "DIAL DIM  OK DEVICES  START POWER"
    )
    return _payload(
        front_images=front_images,
        back_images=[ImageSlot(3, 11, device.kind, 56)],
        front_text=front_text,
        back_text=[
            TextSlot(65, 10, device.name, "normal", WHITE, width=90),
            TextSlot(65, 34, device.state_label, "bold", ACCENT if device.on else MUTED),
            TextSlot(65, 51, _level_bar(device.brightness, 15), "tiny", WHITE),
            TextSlot(65, 61, position, "tiny", MUTED),
            TextSlot(3, 72, hint, "tiny", MUTED),
        ],
    )


def render_demo(demo: BaseDemo) -> types.DisplayElements:
    """Render one of the three UI studies."""
    if isinstance(demo, GridDemo):
        return _grid(demo)
    if isinstance(demo, CapabilitiesDemo):
        return _capabilities(demo)
    if isinstance(demo, FocusDemo):
        return _focus(demo)
    raise TypeError(f"Unsupported demo type: {type(demo).__name__}")
