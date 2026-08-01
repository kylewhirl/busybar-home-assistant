"""Switch entities for BUSY Bar."""

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import BusyBarControllerEntity
from .models import BusyBarConfigEntry


class BusyBarDashboardSwitch(BusyBarControllerEntity, SwitchEntity):
    entity_description = SwitchEntityDescription(
        key="dashboard", translation_key="dashboard", icon="mdi:home-assistant"
    )

    def __init__(self, entry: BusyBarConfigEntry) -> None:
        super().__init__(entry, "dashboard")

    @property
    def is_on(self) -> bool:
        return self.controller.active

    async def async_turn_on(self, **kwargs: object) -> None:
        await self.controller.async_open()

    async def async_turn_off(self, **kwargs: object) -> None:
        await self.controller.async_close()


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BusyBarConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([BusyBarDashboardSwitch(entry)])
