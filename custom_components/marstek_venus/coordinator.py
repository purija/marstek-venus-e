"""DataUpdateCoordinator for Marstek Venus."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .client import MarstekClient
from .const import (
    CONF_ENABLE_MODE,
    CONF_HOST,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_TIMEOUT,
    CONF_VER,
    DEFAULT_ENABLE_CONTROLS,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_TIMEOUT,
    DOMAIN,
    MANUFACTURER,
)

_LOGGER = logging.getLogger(__name__)

# Spacing between requests is enforced by MarstekClient (shared with commands).
# (data key, client method, option that must be on for the query to run or None)
_QUERIES: list[tuple[str, str, str | None]] = [
    ("es_status", "get_es_status", None),   # always reliable — must be first
    ("em_status", "get_em_status", None),
    # Only the optional operating mode select reads this. Without it the query
    # would cost a request plus the 1 s gap on every poll for nothing.
    ("es_mode", "get_es_mode", CONF_ENABLE_MODE),
    ("bat_status", "get_bat_status", None),  # intermittent on fw148 — place last
]


class MarstekCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Polls ES/EM/Bat status (and ES.GetMode if the mode select is on) in turn.

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
        self._queries = [
            (key, method)
            for key, method, option in _QUERIES
            if option is None or entry.options.get(option, DEFAULT_ENABLE_CONTROLS)
        ]
        self.client = MarstekClient(
            host=entry.data[CONF_HOST],
            port=entry.data[CONF_PORT],
            timeout=float(timeout),
        )
        ver = entry.data.get(CONF_VER)
        self.device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.data.get("ble_mac") or entry.data[CONF_HOST])},
            manufacturer=MANUFACTURER,
            model=entry.data.get("device_name", "Marstek Venus"),
            name=entry.title,
            sw_version=str(ver) if ver is not None else None,
        )

    async def _async_update_data(self) -> dict[str, Any]:
        prev = self.data or {}
        data: dict[str, Any] = {}
        any_success = False

        for key, method_name in self._queries:
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
