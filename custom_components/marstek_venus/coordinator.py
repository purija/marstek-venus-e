"""DataUpdateCoordinator for Marstek Venus."""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .client import MarstekClient
from .const import (
    CONF_HOST,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_TIMEOUT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_TIMEOUT,
    DOMAIN,
    MANUFACTURER,
)

_LOGGER = logging.getLogger(__name__)

# Device processes requests sequentially — send one at a time with a pause.
_QUERY_DELAY = 1.0

_QUERIES: list[tuple[str, str]] = [
    ("es_status", "get_es_status"),   # always reliable — must be first
    ("em_status", "get_em_status"),
    ("es_mode",   "get_es_mode"),
    ("bat_status", "get_bat_status"), # intermittent on fw148 — place last
]


class MarstekCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Polls ES/Bat/EM status sequentially.

    The VenusE firmware discards requests that arrive while it is still
    processing a previous one, so all queries are sent one at a time with
    a short pause between them.

    On partial failures the last known value for that endpoint is kept so
    sensors stay available instead of going to "unavailable".
    """

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        timeout = entry.options.get(CONF_TIMEOUT, DEFAULT_TIMEOUT)
        scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
        )
        self.entry = entry
        self.entry_id = entry.entry_id
        self.client = MarstekClient(
            host=entry.data[CONF_HOST],
            port=entry.data[CONF_PORT],
            timeout=float(timeout),
        )
        self.device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.data.get("ble_mac") or entry.data[CONF_HOST])},
            manufacturer=MANUFACTURER,
            model=entry.data.get("device_name", "Marstek Venus"),
            name=entry.title,
        )

    async def _async_update_data(self) -> dict[str, Any]:
        prev = self.data or {}
        data: dict[str, Any] = {}
        any_success = False

        for i, (key, method_name) in enumerate(_QUERIES):
            if i > 0:
                await asyncio.sleep(_QUERY_DELAY)
            try:
                result = await getattr(self.client, method_name)()
                data[key] = result
                any_success = True
            except Exception as err:
                _LOGGER.debug("Failed to fetch %s: %s", key, err)
                # Keep last known value so sensors don't flip to unavailable
                data[key] = prev.get(key, {})

        if not any_success:
            raise UpdateFailed("All device queries failed — check IP and port")

        return data
