"""Number entity for Marstek Venus depth of discharge (DOD)."""
from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import MarstekCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: MarstekCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([MarstekDODNumber(coordinator)])


class MarstekDODNumber(CoordinatorEntity[MarstekCoordinator], NumberEntity):
    """Depth of discharge setting. Range 30–88 %; no GET exists on the device API."""

    _attr_has_entity_name = True
    _attr_name = "Depth of Discharge"
    _attr_native_min_value = 30
    _attr_native_max_value = 88
    _attr_native_step = 1
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_mode = NumberMode.BOX

    def __init__(self, coordinator: MarstekCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry_id}_dod"
        self._attr_device_info = coordinator.device_info
        self._dod_value: int | None = None

    @property
    def native_value(self) -> int | None:
        return self._dod_value

    async def async_set_native_value(self, value: float) -> None:
        int_value = int(value)
        await self.coordinator.client.set_dod(int_value)
        self._dod_value = int_value
        self.async_write_ha_state()
