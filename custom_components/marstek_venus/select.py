"""Select entity for Marstek Venus operating mode."""
from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MODES
from .coordinator import MarstekCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: MarstekCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([MarstekModeSelect(coordinator)])


class MarstekModeSelect(CoordinatorEntity[MarstekCoordinator], SelectEntity):
    _attr_has_entity_name = True
    _attr_name = "Operating Mode"
    _attr_options = MODES

    def __init__(self, coordinator: MarstekCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry_id}_operating_mode"
        self._attr_device_info = coordinator.device_info

    @property
    def current_option(self) -> str | None:
        mode = self.coordinator.data.get("es_mode", {}).get("mode")
        return mode if mode in self._attr_options else None

    async def async_select_option(self, option: str) -> None:
        if option == "Passive":
            await self.coordinator.client.set_passive_mode(power=0, cd_time=0)
        else:
            await self.coordinator.client.set_mode(option)
        await self.coordinator.async_request_refresh()
