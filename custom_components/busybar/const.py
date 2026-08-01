"""Constants for the BUSY Bar integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "busybar"
NAME: Final = "BUSY Bar"
MANUFACTURER: Final = "Flipper Devices"
MODEL: Final = "BUSY Bar"

CONF_ACCESS_KEY: Final = "access_key"
CONF_ENTITIES: Final = "entities"
CONF_ACCENT_COLOR: Final = "accent_color"
CONF_DIAL_STEP: Final = "dial_step"
CONF_DISPLAY_PRIORITY: Final = "display_priority"

DEFAULT_HOST: Final = "10.0.4.20"
DEFAULT_ACCENT_COLOR: Final = "#63E6BE"
DEFAULT_DIAL_STEP: Final = 5
DEFAULT_DISPLAY_PRIORITY: Final = 100
LEGACY_DEFAULT_DISPLAY_PRIORITY: Final = 95
DEFAULT_SCAN_INTERVAL: Final = 30

APPLICATION_NAME: Final = "home_assistant"
EVENT_INPUT: Final = "busybar_input"

PLATFORMS: Final = ["binary_sensor", "button", "number", "sensor", "switch"]

SUPPORTED_DOMAINS: Final = (
    "button",
    "climate",
    "cover",
    "fan",
    "input_boolean",
    "input_number",
    "light",
    "lock",
    "media_player",
    "number",
    "scene",
    "script",
    "switch",
)
