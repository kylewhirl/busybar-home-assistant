"""Config flow for BUSY Bar."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from busylib import exceptions
from homeassistant import config_entries
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .client import async_create_client
from .const import (
    CONF_ACCENT_COLOR,
    CONF_ACCESS_KEY,
    CONF_DIAL_STEP,
    CONF_DISPLAY_PRIORITY,
    CONF_ENTITIES,
    DEFAULT_DIAL_STEP,
    DEFAULT_DISPLAY_PRIORITY,
    DEFAULT_HOST,
    DOMAIN,
    SUPPORTED_DOMAINS,
)

_LOGGER = logging.getLogger(__name__)


async def _validate_input(hass: HomeAssistant, data: dict[str, Any]) -> tuple[str, str]:
    """Connect and return the device serial and title."""
    client = await async_create_client(hass, data[CONF_HOST], data[CONF_ACCESS_KEY])
    try:
        status = await client.status()
    finally:
        await client.aclose()

    serial = status.device.serial_number
    return serial, f"BUSY Bar {serial[-4:]}"


class BusyBarConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for BUSY Bar."""

    VERSION = 2

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                serial, title = await _validate_input(self.hass, user_input)
            except exceptions.BusyBarAPIError as err:
                if err.status_code in (401, 403):
                    errors["base"] = "invalid_auth"
                else:
                    errors["base"] = "cannot_connect"
            except exceptions.BusyBarError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected error connecting to BUSY Bar")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(serial)
                self._abort_if_unique_id_configured(updates={CONF_HOST: user_input[CONF_HOST]})
                return self.async_create_entry(title=title, data=user_input)

        schema = vol.Schema(
            {
                vol.Required(CONF_HOST, default=DEFAULT_HOST): str,
                vol.Required(CONF_ACCESS_KEY): selector.TextSelector(
                    selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
                ),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> BusyBarOptionsFlow:
        """Return the options flow."""
        return BusyBarOptionsFlow(config_entry)


class BusyBarOptionsFlow(config_entries.OptionsFlow):
    """Configure the BUSY Bar dashboard."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Manage dashboard options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options = self._entry.options
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_ENTITIES, default=options.get(CONF_ENTITIES, [])
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain=list(SUPPORTED_DOMAINS), multiple=True)
                ),
                vol.Required(
                    CONF_ACCENT_COLOR,
                    default=options.get(CONF_ACCENT_COLOR, [99, 230, 190]),
                ): selector.ColorRGBSelector(),
                vol.Required(
                    CONF_DIAL_STEP,
                    default=options.get(CONF_DIAL_STEP, DEFAULT_DIAL_STEP),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=1,
                        max=25,
                        step=1,
                        mode=selector.NumberSelectorMode.SLIDER,
                        unit_of_measurement="%",
                    )
                ),
                vol.Required(
                    CONF_DISPLAY_PRIORITY,
                    default=options.get(CONF_DISPLAY_PRIORITY, DEFAULT_DISPLAY_PRIORITY),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=1,
                        max=100,
                        step=1,
                        mode=selector.NumberSelectorMode.SLIDER,
                    )
                ),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
