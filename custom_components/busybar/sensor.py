"""Sensors for BUSY Bar."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import BusyBarControllerEntity, BusyBarEntity
from .models import BusyBarConfigEntry, BusyBarData


class BusyBarDiagnosticSensor(BusyBarEntity, SensorEntity):
    """A polled BUSY Bar sensor."""

    def __init__(
        self,
        entry: BusyBarConfigEntry,
        description: SensorEntityDescription,
        value_fn: Callable[[BusyBarData], Any],
    ) -> None:
        super().__init__(entry, description.key)
        self.entity_description = description
        self._value_fn = value_fn

    @property
    def native_value(self) -> Any:
        return self._value_fn(self.coordinator.data)


class BusyBarNavigationSensor(BusyBarControllerEntity, SensorEntity):
    def __init__(self, entry: BusyBarConfigEntry) -> None:
        super().__init__(entry, "navigation")
        self._attr_translation_key = "navigation"

    @property
    def native_value(self) -> str:
        return self.controller.navigation.value


class BusyBarSelectedSensor(BusyBarControllerEntity, SensorEntity):
    def __init__(self, entry: BusyBarConfigEntry) -> None:
        super().__init__(entry, "selected_accessory")
        self._attr_translation_key = "selected_accessory"

    @property
    def native_value(self) -> str | None:
        return self.controller.selected_name

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"entity_id": self.controller.selected_entity_id}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BusyBarConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities(
        [
            BusyBarDiagnosticSensor(
                entry,
                SensorEntityDescription(
                    key="battery",
                    translation_key="battery",
                    device_class=SensorDeviceClass.BATTERY,
                    native_unit_of_measurement=PERCENTAGE,
                    state_class=SensorStateClass.MEASUREMENT,
                ),
                lambda data: data.status.power.battery_charge,
            ),
            BusyBarDiagnosticSensor(
                entry,
                SensorEntityDescription(
                    key="firmware",
                    translation_key="firmware",
                    entity_registry_enabled_default=False,
                ),
                lambda data: data.status.firmware.version,
            ),
            BusyBarNavigationSensor(entry),
            BusyBarSelectedSensor(entry),
        ]
    )
