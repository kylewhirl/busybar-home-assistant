"""Runtime models for the BUSY Bar integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from homeassistant.config_entries import ConfigEntry

if TYPE_CHECKING:
    from busylib import AsyncBusyBar

    from .controller import BusyBarController
    from .coordinator import BusyBarCoordinator


@dataclass(slots=True)
class BusyBarData:
    """Latest polled device data."""

    status: Any
    display_brightness: Any


@dataclass(slots=True)
class BusyBarRuntime:
    """Objects owned by one config entry."""

    client: AsyncBusyBar
    coordinator: BusyBarCoordinator
    controller: BusyBarController


type BusyBarConfigEntry = ConfigEntry[BusyBarRuntime]
