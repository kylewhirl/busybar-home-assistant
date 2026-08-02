"""One fixed-slot BUSY Canvas UI with progressively deeper screens."""

from __future__ import annotations

from dataclasses import dataclass

from busylib import types

from .icons import APPLICATION_NAME, asset_path
from .models import BaseDemo, DemoView, HomeFlowDemo

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
    variant: str | None = None


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
        (types.DisplayName.FRONT, "fi", front_images, 4),
        (types.DisplayName.BACK, "bi", back_images, 4),
    ):
        padded = slots + [ImageSlot()] * (count - len(slots))
        for index, slot in enumerate(padded[:count]):
            path = asset_path(slot.kind, slot.size, slot.variant) if slot.kind else "demo_blank.png"
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


def _level_bar(level: int, width: int = 18) -> str:
    filled = round(width * level / 100)
    return "=" * filled + "-" * (width - filled)


def _accessories_screen(demo: HomeFlowDemo) -> types.DisplayElements:
    """Show four accessories at once and enlarge the selected one."""
    front_images = []
    front_text = []
    for index, device in enumerate(demo.devices[:4]):
        selected = index == demo.selected
        front_images.append(
            ImageSlot(
                index * 18 + 2,
                1,
                device.kind,
                14,
                "active" if selected else "inactive",
            )
        )
    images = [
        ImageSlot(3, 11 + index * 15, device.kind, 14) for index, device in enumerate(demo.devices)
    ]
    text = [
        TextSlot(
            3,
            1,
            f"ACCESSORIES  {demo.selected + 1}/{len(demo.devices)}",
            "tiny",
            MUTED,
        )
    ]
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


def _property_value(demo: HomeFlowDemo, name: str) -> str:
    if name == "brightness":
        return f"{demo.device.brightness}%"
    if name == "color":
        return demo.device.color_label
    return f"{demo.device.kelvin}K"


def _controls_screen(demo: HomeFlowDemo) -> types.DisplayElements:
    device = demo.device
    editing = demo.view == DemoView.EDIT
    labels = ("BRIGHT", "COLOR", "TEMP")
    front_images = [
        ImageSlot(
            1,
            1,
            device.kind,
            14,
            "active" if device.on else "inactive",
        )
    ]
    front_text = [
        TextSlot(
            18,
            0,
            labels[demo.property_index],
            "tiny",
            ACCENT,
        )
    ]
    front_text.extend(
        [
            TextSlot(
                18,
                8,
                _property_value(demo, demo.property_name),
                "small",
                ACCENT if editing else WHITE,
            ),
            TextSlot(
                70,
                0,
                f"{demo.property_index + 1}/{len(demo.properties)}",
                "tiny",
                DIM,
                "top_right",
            ),
            TextSlot(70, 8, "EDIT" if editing else "", "tiny", ACCENT, "top_right"),
        ]
    )
    if demo.view == DemoView.PROPERTIES:
        # A compact property picker: the three controls remain visible while
        # the active one is bracketed, so the dial's destination is obvious.
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
        front_text=front_text,
        back_text=[
            TextSlot(42, 10, property_name.upper(), "small", MUTED),
            TextSlot(42, 27, value, "large", ACCENT),
            TextSlot(
                42,
                55,
                _level_bar(device.brightness)
                if property_name == "brightness"
                else device.color_label
                if property_name == "color"
                else "COOL <-----> WARM",
                "tiny",
                WHITE,
            ),
            TextSlot(5, 72, "DIAL CHANGE  OK DONE  START POWER", "tiny", MUTED),
        ],
    )


def render_demo(demo: BaseDemo) -> types.DisplayElements:
    """Render the current screen using one stable BUSY Canvas layout."""
    if not isinstance(demo, HomeFlowDemo):
        raise TypeError(f"Unsupported demo type: {type(demo).__name__}")
    if demo.view == DemoView.BROWSE:
        return _accessories_screen(demo)
    return _controls_screen(demo)
