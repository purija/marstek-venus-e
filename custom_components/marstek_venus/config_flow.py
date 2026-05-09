"""Config flow and options flow for Marstek Venus integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .client import MarstekClient, MarstekError
from .const import (
    CONF_HOST,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_TIMEOUT,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_TIMEOUT,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

_SETUP_SCHEMA = vol.Schema({
    vol.Required(CONF_HOST): str,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): vol.All(int, vol.Range(min=1, max=65535)),
})


class MarstekConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> MarstekOptionsFlow:
        return MarstekOptionsFlow(config_entry)

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            client = MarstekClient(
                host=user_input[CONF_HOST],
                port=user_input[CONF_PORT],
                timeout=float(DEFAULT_TIMEOUT),
            )
            try:
                # ES.GetStatus is the most reliable endpoint on all firmware versions
                await client.get_es_status()
            except MarstekError as err:
                _LOGGER.debug("MarstekError during config: %s", err)
                errors["base"] = "cannot_connect"
            except (TimeoutError, OSError):
                errors["base"] = "timeout"
            except Exception:
                _LOGGER.exception("Unexpected error during Marstek config flow")
                errors["base"] = "unknown"
            else:
                # get_device() may return a Parse error for unicast — treat as optional
                try:
                    device_info = await client.get_device()
                except Exception:
                    device_info = {}
                ble_mac = device_info.get("ble_mac", "")
                device_name = device_info.get("device", "Marstek Venus")

                await self.async_set_unique_id(ble_mac or user_input[CONF_HOST])
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=device_name,
                    data={
                        CONF_HOST: user_input[CONF_HOST],
                        CONF_PORT: user_input[CONF_PORT],
                        "device_name": device_name,
                        "ble_mac": ble_mac,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=_SETUP_SCHEMA,
            errors=errors,
        )


class MarstekOptionsFlow(config_entries.OptionsFlow):
    """Options flow: configure timeout and polling interval."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        opts = self._entry.options

        if user_input is not None:
            return self.async_create_entry(title="", data={
                **opts,
                CONF_TIMEOUT: user_input[CONF_TIMEOUT],
                CONF_SCAN_INTERVAL: user_input[CONF_SCAN_INTERVAL],
            })

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Optional(
                    CONF_TIMEOUT,
                    default=opts.get(CONF_TIMEOUT, DEFAULT_TIMEOUT),
                ): vol.All(int, vol.Range(min=5, max=30)),
                vol.Optional(
                    CONF_SCAN_INTERVAL,
                    default=opts.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                ): vol.All(int, vol.Range(min=15, max=300)),
            }),
        )
