"""BUSY API client construction helpers."""

from __future__ import annotations

from functools import partial

from busylib import AsyncBusyBar
from homeassistant.core import HomeAssistant


async def async_create_client(hass: HomeAssistant, host: str, access_key: str) -> AsyncBusyBar:
    """Create a BUSY client without blocking Home Assistant's event loop.

    ``AsyncBusyBar`` builds its TLS context during construction. Home Assistant
    treats that filesystem access as blocking, so construction belongs in the
    executor even though subsequent client calls are asynchronous.
    """
    return await hass.async_add_executor_job(
        partial(AsyncBusyBar, host, token=access_key)
    )
