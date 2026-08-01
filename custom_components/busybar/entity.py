"""Entity helpers for BUSY Bar."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, MODEL
from .coordinator import BusyBarCoordinator
from .models import BusyBarConfigEntry


class BusyBarEntity(CoordinatorEntity[BusyBarCoordinator]):
    """Base entity tied to one BUSY Bar."""

    _attr_has_entity_name = True

    def __init__(self, entry: BusyBarConfigEntry, key: str) -> None:
        super().__init__(entry.runtime_data.coordinator)
        self.entry = entry
        self.controller = entry.runtime_data.controller
        serial = self.coordinator.data.status.device.serial_number
        self._attr_unique_id = f"{serial}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, serial)},
            manufacturer=MANUFACTURER,
            model=MODEL,
            name=entry.title,
            serial_number=serial,
            sw_version=self.coordinator.data.status.firmware.version,
        )


class BusyBarControllerEntity(BusyBarEntity):
    """Entity that also updates when navigation state changes."""

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(self.controller.add_listener(self.async_write_ha_state))
