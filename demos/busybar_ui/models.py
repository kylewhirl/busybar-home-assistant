"""State machines for standalone BUSY Bar UI studies."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Literal


class DemoView(StrEnum):
    """Shared navigation depth."""

    BROWSE = "browse"
    CONTROL = "control"
    PROPERTIES = "properties"
    EDIT = "edit"


@dataclass
class DemoDevice:
    """Local fake accessory; no Home Assistant state is involved."""

    name: str
    kind: str = "light"
    on: bool = True
    brightness: int = 70
    color_index: int = 0
    kelvin: int = 3200

    @property
    def state_label(self) -> str:
        return f"{'ON' if self.on else 'OFF'} {self.brightness if self.on else 0}%"

    @property
    def color_label(self) -> str:
        return ("MINT", "AMBER", "BLUE", "ROSE", "LIME", "VIOLET")[self.color_index]

    def toggle(self) -> None:
        self.on = not self.on

    def adjust_brightness(self, delta: int) -> None:
        self.brightness = max(0, min(100, self.brightness + delta * 5))
        self.on = self.brightness > 0


def fake_devices() -> list[DemoDevice]:
    """Return a fresh, intentionally varied fake home."""
    return [
        DemoDevice("Studio Lamp", "light", True, 80, 0, 3000),
        DemoDevice("Desk Lamp", "desk_lamp", True, 45, 2, 4200),
        DemoDevice("Hall Light", "light", False, 65, 1, 2700),
        DemoDevice("Air Purifier", "fan", True, 35, 0, 3200),
    ]


@dataclass
class BaseDemo:
    """Common fake-device interactions."""

    devices: list[DemoDevice] = field(default_factory=fake_devices)
    selected: int = 0
    view: DemoView = DemoView.BROWSE

    @property
    def device(self) -> DemoDevice:
        return self.devices[self.selected]

    def move_device(self, delta: int) -> None:
        self.selected = (self.selected + delta) % len(self.devices)

    def handle(self, event_type: str, value: Any) -> bool:
        """Apply one input and return False when the demo should exit."""
        raise NotImplementedError

    def _handle_common_button(self, button: str) -> bool | None:
        if button == "back":
            return False
        if button == "start":
            self.device.toggle()
            return True
        return None


@dataclass
class GridDemo(BaseDemo):
    """Four-device list with a focused brightness view."""

    def handle(self, event_type: str, value: Any) -> bool:
        if event_type == "encoder":
            if self.view == DemoView.BROWSE:
                self.move_device(int(value))
            else:
                self.device.adjust_brightness(int(value))
            return True
        if event_type != "button":
            return True
        common = self._handle_common_button(str(value))
        if common is not None:
            return common
        if value == "ok":
            self.view = (
                DemoView.CONTROL if self.view == DemoView.BROWSE else DemoView.BROWSE
            )
        return True


PropertyName = Literal["brightness", "color", "temperature"]


@dataclass
class CapabilitiesDemo(BaseDemo):
    """One light with a property selector and dedicated editors."""

    properties: tuple[PropertyName, ...] = ("brightness", "color", "temperature")
    property_index: int = 0

    @property
    def property_name(self) -> PropertyName:
        return self.properties[self.property_index]

    def handle(self, event_type: str, value: Any) -> bool:
        if event_type == "encoder":
            delta = int(value)
            if self.view == DemoView.BROWSE:
                self.move_device(delta)
            elif self.view == DemoView.PROPERTIES:
                self.property_index = (self.property_index + delta) % len(self.properties)
            elif self.view == DemoView.EDIT:
                self._adjust_property(delta)
            return True
        if event_type != "button":
            return True
        common = self._handle_common_button(str(value))
        if common is not None:
            return common
        if value == "ok":
            if self.view == DemoView.BROWSE:
                self.view = DemoView.PROPERTIES
            elif self.view == DemoView.PROPERTIES:
                self.view = DemoView.EDIT
            else:
                self.view = DemoView.PROPERTIES
        return True

    def _adjust_property(self, delta: int) -> None:
        if self.property_name == "brightness":
            self.device.adjust_brightness(delta)
        elif self.property_name == "color":
            self.device.color_index = (self.device.color_index + delta) % 6
            self.device.on = True
        else:
            self.device.kelvin = max(2200, min(6500, self.device.kelvin + delta * 200))
            self.device.on = True


@dataclass
class FocusDemo(BaseDemo):
    """Large-icon carousel with only one accessory competing for attention."""

    def handle(self, event_type: str, value: Any) -> bool:
        if event_type == "encoder":
            if self.view == DemoView.BROWSE:
                self.move_device(int(value))
            else:
                self.device.adjust_brightness(int(value))
            return True
        if event_type != "button":
            return True
        common = self._handle_common_button(str(value))
        if common is not None:
            return common
        if value == "ok":
            self.view = (
                DemoView.CONTROL if self.view == DemoView.BROWSE else DemoView.BROWSE
            )
        return True


def parse_input_updates(message: dict[str, Any]) -> list[tuple[str, Any]]:
    """Normalize BUSY status-stream messages without importing Home Assistant."""
    events: list[tuple[str, Any]] = []
    for update in message.get("updates", []):
        input_update = update.get("input", {})
        if "button_event" in input_update:
            button = input_update.get("button_event") or {}
            action = str(button.get("action", "")).lower()
            if action in ("", "press"):
                events.append(("button", str(button.get("button") or "ok").lower()))
        if encoder := input_update.get("encoder_event"):
            delta = int(encoder.get("delta", 0))
            if delta:
                events.append(("encoder", delta))
    return events
