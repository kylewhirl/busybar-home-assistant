"""Number entities for BUSY Bar."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import BusyBarEntity
from .models import BusyBarConfigEntry


class BusyBarDisplayBrightness(BusyBarEntity, NumberEntity):
    """Set a fixed display brightness; Auto is represented as unavailable."""

    entity_description = NumberEntityDescription(
        key="display_brightness",
        translation_key="display_brightness",
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        native_unit_of_measurement=PERCENTAGE,
    )

    def __init__(self, entry: BusyBarConfigEntry) -> None:
        super().__init__(entry, "display_brightness")

    @property
    def native_value(self) -> float | None:
        value = self.coordinator.data.display_brightness.value
        try:
            return float(value)
        except TypeError, ValueError:
            return None

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.client.display_brightness_set(round(value))
        await self.coordinator.async_request_refresh()


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BusyBarConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([BusyBarDisplayBrightness(entry)])
