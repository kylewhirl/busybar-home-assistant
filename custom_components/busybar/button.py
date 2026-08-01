"""Button entities for BUSY Bar."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import BusyBarControllerEntity
from .models import BusyBarConfigEntry


class BusyBarActionButton(BusyBarControllerEntity, ButtonEntity):
    def __init__(
        self,
        entry: BusyBarConfigEntry,
        description: ButtonEntityDescription,
        action: Callable[[], Awaitable[None]],
    ) -> None:
        super().__init__(entry, description.key)
        self.entity_description = description
        self._action = action

    async def async_press(self) -> None:
        await self._action()


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BusyBarConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    controller = entry.runtime_data.controller
    async_add_entities(
        [
            BusyBarActionButton(
                entry,
                ButtonEntityDescription(
                    key="previous_accessory",
                    translation_key="previous_accessory",
                    icon="mdi:chevron-left",
                ),
                lambda: controller.async_select_relative(-1),
            ),
            BusyBarActionButton(
                entry,
                ButtonEntityDescription(
                    key="next_accessory",
                    translation_key="next_accessory",
                    icon="mdi:chevron-right",
                ),
                lambda: controller.async_select_relative(1),
            ),
            BusyBarActionButton(
                entry,
                ButtonEntityDescription(
                    key="refresh_dashboard",
                    translation_key="refresh_dashboard",
                    icon="mdi:refresh",
                ),
                controller.async_render,
            ),
        ]
    )
