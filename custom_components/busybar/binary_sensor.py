"""Binary sensors for BUSY Bar."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import BusyBarControllerEntity
from .models import BusyBarConfigEntry


class BusyBarConnectedSensor(BusyBarControllerEntity, BinarySensorEntity):
    """Report whether both polling and the input stream are healthy."""

    entity_description = BinarySensorEntityDescription(
        key="connected",
        translation_key="connected",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
    )

    def __init__(self, entry: BusyBarConfigEntry) -> None:
        super().__init__(entry, "connected")

    @property
    def is_on(self) -> bool:
        return self.coordinator.last_update_success and self.controller.stream_connected


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BusyBarConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([BusyBarConnectedSensor(entry)])
