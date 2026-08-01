"""Pixel dashboard rendering and navigation primitives."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from busylib import types

from .const import APPLICATION_NAME


class NavigationState(StrEnum):
    """Current dashboard level."""

    INACTIVE = "inactive"
    BROWSE = "browse"
    CONTROL = "control"


def button_transition(
    navigation: NavigationState, button: str, has_accessory: bool
) -> tuple[NavigationState, bool]:
    """Return the next view and whether the selected accessory should activate."""
    if button == "ok":
        if navigation == NavigationState.INACTIVE:
            return NavigationState.BROWSE, False
        if navigation == NavigationState.BROWSE and has_accessory:
            return NavigationState.CONTROL, False
    elif button == "back":
        if navigation == NavigationState.CONTROL:
            return NavigationState.BROWSE, False
        if navigation == NavigationState.BROWSE:
            return NavigationState.INACTIVE, False
    elif (
        button == "start"
        and navigation in (NavigationState.BROWSE, NavigationState.CONTROL)
        and has_accessory
    ):
        return navigation, True
    return navigation, False


def clamp(value: float, minimum: float, maximum: float) -> float:
    """Clamp a number to a range."""
    return max(minimum, min(maximum, value))


def brightness_to_percent(value: int | None) -> int:
    """Convert Home Assistant's 0..255 brightness into a percentage."""
    if value is None:
        return 100
    return round(clamp(value, 0, 255) * 100 / 255)


def percent_to_brightness(value: float) -> int:
    """Convert a percentage into Home Assistant's 0..255 brightness."""
    return round(clamp(value, 0, 100) * 255 / 100)


def apply_dial_delta(current: float, delta: int, step: float) -> int:
    """Apply an encoder delta to a percent-like value."""
    return round(clamp(current + delta * step, 0, 100))


def parse_input_updates(message: dict[str, Any]) -> list[tuple[str, Any]]:
    """Normalize BUSY WebSocket input updates into small event tuples."""
    events: list[tuple[str, Any]] = []
    for update in message.get("updates", []):
        input_update = update.get("input", {})
        if button := input_update.get("button_event"):
            if str(button.get("action", "")).lower() == "press":
                events.append(("button", str(button.get("button", "")).lower()))
        if encoder := input_update.get("encoder_event"):
            delta = int(encoder.get("delta", 0))
            if delta:
                events.append(("encoder", delta))
        if switch := input_update.get("switch_event"):
            events.append(("switch", str(switch.get("position", "")).lower()))
    return events


def icon_asset_path(display: types.DisplayName, domain: str) -> str:
    """Return the uploaded icon filename, falling back to a generic device."""
    safe_domain = domain if domain.replace("_", "").isalnum() else "device"
    return f"ha_{display.value}_{safe_domain}.png"


def build_dashboard_payload(
    *,
    domain: str,
    name: str,
    state_label: str,
    navigation: NavigationState,
    accent_color: str,
    priority: int,
    position: tuple[int, int],
    level: int | None = None,
) -> types.DisplayElements:
    """Build a single draw payload spanning the front and back displays."""
    current, total = position
    front_text_color = (
        accent_color if state_label.lower() not in ("off", "closed", "locked") else "#64748B"
    )
    label = "BROWSE" if navigation == NavigationState.BROWSE else "CONTROL"
    level_suffix = f"  ·  {level}%" if level is not None else ""

    elements: list[types.DisplayElement] = [
        types.ImageElement(
            id="front_icon",
            display=types.DisplayName.FRONT,
            x=1,
            y=2,
            path=icon_asset_path(types.DisplayName.FRONT, domain),
        ),
        types.ImageElement(
            id="back_icon",
            display=types.DisplayName.BACK,
            x=8,
            y=15,
            path=icon_asset_path(types.DisplayName.BACK, domain),
        ),
        types.TextElement(
            id="front_name",
            display=types.DisplayName.FRONT,
            x=16,
            y=1,
            width=54,
            text=name,
            font="tiny",
            color=front_text_color,
            scroll_rate=70,
            scroll_start_delay=200,
            scroll_repeat_delay=250,
        ),
        types.TextElement(
            id="front_state",
            display=types.DisplayName.FRONT,
            x=16,
            y=8,
            text=f"{state_label}{f' {level}%' if level is not None else ''}",
            font="small",
            color="#FFFFFFFF",
        ),
        types.TextElement(
            id="front_mode",
            display=types.DisplayName.FRONT,
            x=70,
            y=8,
            align="top_right",
            text="SELECT" if navigation == NavigationState.BROWSE else "ADJUST",
            font="tiny",
            color=accent_color,
        ),
        types.TextElement(
            id="back_kicker",
            display=types.DisplayName.BACK,
            x=58,
            y=8,
            text=f"HOME ASSISTANT  {current}/{total}",
            font="tiny",
            color="#999999FF",
        ),
        types.TextElement(
            id="back_name",
            display=types.DisplayName.BACK,
            x=58,
            y=25,
            width=96,
            text=name,
            font="normal",
            color="#FFFFFFFF",
            scroll_rate=55,
            scroll_start_delay=300,
            scroll_repeat_delay=350,
        ),
        types.TextElement(
            id="back_state",
            display=types.DisplayName.BACK,
            x=58,
            y=47,
            text=(f"{domain.replace('_', ' ').upper()}  ·  {state_label.upper()}{level_suffix}"),
            font="small",
            color="#CCCCCCFF",
        ),
        types.TextElement(
            id="back_hint",
            display=types.DisplayName.BACK,
            x=8,
            y=68,
            text=(
                "DIAL: BROWSE   SELECT: ADJUST   START: TOGGLE"
                if navigation == NavigationState.BROWSE
                else "DIAL: ADJUST   START: TOGGLE   BACK: LIST"
            ),
            font="tiny",
            color="#888888FF",
        ),
        types.TextElement(
            id="back_mode",
            display=types.DisplayName.BACK,
            x=152,
            y=8,
            align="top_right",
            text=label,
            font="tiny",
            color="#777777FF",
        ),
    ]

    if level is not None:
        front_ticks = 9
        back_ticks = 24
        elements.extend(
            [
                types.TextElement(
                    id="front_level",
                    display=types.DisplayName.FRONT,
                    x=16,
                    y=14,
                    text=(
                        "|" * round(front_ticks * level / 100)
                        + "." * (front_ticks - round(front_ticks * level / 100))
                    ),
                    font="tiny",
                    color=front_text_color,
                ),
                types.TextElement(
                    id="back_level",
                    display=types.DisplayName.BACK,
                    x=8,
                    y=60,
                    text=(
                        "=" * round(back_ticks * level / 100)
                        + "-" * (back_ticks - round(back_ticks * level / 100))
                    ),
                    font="tiny",
                    color="#FFFFFFFF",
                ),
            ]
        )

    return types.DisplayElements(
        application_name=APPLICATION_NAME,
        priority=priority,
        elements=elements,
    )


def build_message_payload(text: str, color: str, priority: int) -> types.DisplayElements:
    """Build a temporary message for both displays."""
    return types.DisplayElements(
        application_name=APPLICATION_NAME,
        priority=priority,
        elements=[
            types.TextElement(
                id="front_message",
                display=types.DisplayName.FRONT,
                x=36,
                y=8,
                align="center",
                width=70,
                text=text,
                font="small",
                color=color,
                scroll_rate=25,
            ),
            types.TextElement(
                id="back_message_title",
                display=types.DisplayName.BACK,
                x=80,
                y=20,
                align="top_mid",
                text="HOME ASSISTANT",
                font="tiny",
                color="#888888FF",
            ),
            types.TextElement(
                id="back_message",
                display=types.DisplayName.BACK,
                x=80,
                y=42,
                align="center",
                width=150,
                text=text,
                font="normal",
                color="#FFFFFFFF",
                scroll_rate=30,
            ),
        ],
    )
