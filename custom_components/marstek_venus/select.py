"""Select entity for Marstek Venus operating mode (optional)."""
from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_ENABLE_MODE, DEFAULT_ENABLE_CONTROLS, DOMAIN, MODES, UID_MODE
from .coordinator import MarstekCoordinator
from .entity import MarstekControlEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    if not entry.options.get(CONF_ENABLE_MODE, DEFAULT_ENABLE_CONTROLS):
        return
    coordinator: MarstekCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([MarstekModeSelect(coordinator)])


class MarstekModeSelect(MarstekControlEntity, SelectEntity):
    """Operating mode (Auto / AI / UPS).

    Manual and Passive are not selectable: both need parameters (time slots,
    target power) and would misconfigure the device without them. If the
    device is in one of those modes (e.g. set via the app) the state is unknown.
    """

    _attr_name = "Operating Mode"
    _attr_options = MODES
    _unique_suffix = UID_MODE

    @property
    def current_option(self) -> str | None:
        mode = (self.coordinator.data or {}).get("es_mode", {}).get("mode")
        if not isinstance(mode, str):
            return None
        # The API doc writes "Ups" in the mode table but "UPS" in its examples,
        # so compare case-insensitively and report our own spelling.
        return next((m for m in MODES if m.lower() == mode.lower()), None)

    async def async_select_option(self, option: str) -> None:
        await self._async_send(self.coordinator.client.set_mode(option))
        # Show the new mode right away instead of polling all four endpoints
        # again; the next regular poll confirms it.
        data = dict(self.coordinator.data)
        data["es_mode"] = {**data.get("es_mode", {}), "mode": option}
        self.coordinator.async_set_updated_data(data)
