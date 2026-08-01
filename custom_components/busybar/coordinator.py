"""Data coordinator for BUSY Bar."""

from __future__ import annotations

import logging
from datetime import timedelta

from busylib import AsyncBusyBar, exceptions
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN
from .models import BusyBarData

_LOGGER = logging.getLogger(__name__)


class BusyBarCoordinator(DataUpdateCoordinator[BusyBarData]):
    """Poll the slower BUSY Bar diagnostics while input arrives by push."""

    def __init__(self, hass: HomeAssistant, client: AsyncBusyBar) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        self.client = client

    async def _async_update_data(self) -> BusyBarData:
        try:
            status = await self.client.status()
            brightness = await self.client.display_brightness()
        except exceptions.BusyBarError as err:
            raise UpdateFailed(f"BUSY Bar update failed: {err}") from err
        return BusyBarData(status=status, display_brightness=brightness)
