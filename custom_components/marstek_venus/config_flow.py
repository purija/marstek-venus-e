"""Config flow for Marstek Venus integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .client import MarstekClient, MarstekError
from .const import CONF_HOST, CONF_PORT, DEFAULT_PORT, DEFAULT_TIMEOUT, DOMAIN

_LOGGER = logging.getLogger(__name__)

_SCHEMA = vol.Schema({
    vol.Required(CONF_HOST): str,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): vol.All(int, vol.Range(min=1, max=65535)),
})


class MarstekConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            client = MarstekClient(
                host=user_input[CONF_HOST],
                port=user_input[CONF_PORT],
                timeout=DEFAULT_TIMEOUT,
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
            data_schema=_SCHEMA,
            errors=errors,
        )
