"""Home Assistant integration for BUSY Bar."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from .client import async_create_client
from .const import CONF_ACCESS_KEY, DOMAIN, PLATFORMS
from .controller import BusyBarController
from .coordinator import BusyBarCoordinator
from .models import BusyBarConfigEntry, BusyBarRuntime

SERVICE_SHOW_MESSAGE = "show_message"
SERVICE_CLEAR_DISPLAY = "clear_display"
SERVICE_REFRESH_DASHBOARD = "refresh_dashboard"


def _service_entries(hass: HomeAssistant, entry_id: str | None) -> list[BusyBarConfigEntry]:
    entries = [
        entry
        for entry in hass.config_entries.async_entries(DOMAIN)
        if entry.state == ConfigEntryState.LOADED and entry.runtime_data
    ]
    if entry_id:
        return [entry for entry in entries if entry.entry_id == entry_id]
    return entries


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Register integration-wide services."""

    async def show_message(call: ServiceCall) -> None:
        for entry in _service_entries(hass, call.data.get("config_entry_id")):
            await entry.runtime_data.controller.async_show_message(
                call.data["text"], call.data.get("color"), call.data["duration"]
            )

    async def clear_display(call: ServiceCall) -> None:
        for entry in _service_entries(hass, call.data.get("config_entry_id")):
            await entry.runtime_data.controller.async_clear_display()

    async def refresh_dashboard(call: ServiceCall) -> None:
        for entry in _service_entries(hass, call.data.get("config_entry_id")):
            await entry.runtime_data.controller.async_render()

    hass.services.async_register(
        DOMAIN,
        SERVICE_SHOW_MESSAGE,
        show_message,
        schema=vol.Schema(
            {
                vol.Required("text"): cv.string,
                vol.Optional("color"): vol.Any(
                    cv.string,
                    vol.All(
                        [vol.All(vol.Coerce(int), vol.Range(min=0, max=255))],
                        vol.Length(min=3, max=3),
                    ),
                ),
                vol.Optional("duration", default=3): vol.All(
                    vol.Coerce(float), vol.Range(min=0.5, max=120)
                ),
                vol.Optional("config_entry_id"): cv.string,
            }
        ),
    )
    common_schema = vol.Schema({vol.Optional("config_entry_id"): cv.string})
    hass.services.async_register(DOMAIN, SERVICE_CLEAR_DISPLAY, clear_display, schema=common_schema)
    hass.services.async_register(
        DOMAIN, SERVICE_REFRESH_DASHBOARD, refresh_dashboard, schema=common_schema
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: BusyBarConfigEntry) -> bool:
    """Set up BUSY Bar from a config entry."""
    client = await async_create_client(
        hass, entry.data[CONF_HOST], entry.data[CONF_ACCESS_KEY]
    )
    coordinator = BusyBarCoordinator(hass, client)
    await coordinator.async_config_entry_first_refresh()

    controller = BusyBarController(hass, entry, client)
    entry.runtime_data = BusyBarRuntime(
        client=client, coordinator=coordinator, controller=controller
    )
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await controller.async_start()
    return True


async def async_unload_entry(hass: HomeAssistant, entry: BusyBarConfigEntry) -> bool:
    """Unload a BUSY Bar config entry."""
    await entry.runtime_data.controller.async_stop()
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    await entry.runtime_data.client.aclose()
    return unload_ok


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload after dashboard options change."""
    await hass.config_entries.async_reload(entry.entry_id)
