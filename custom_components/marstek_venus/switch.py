"""Switch entity for Marstek Venus LED panel."""
from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
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
    async_add_entities([MarstekLEDSwitch(coordinator)])


class MarstekLEDSwitch(CoordinatorEntity[MarstekCoordinator], SwitchEntity):
    """LED panel switch. State is tracked locally — no GET exists on the API."""

    _attr_has_entity_name = True
    _attr_name = "LED Panel"

    def __init__(self, coordinator: MarstekCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry_id}_led"
        self._attr_device_info = coordinator.device_info
        self._is_on: bool = False

    @property
    def is_on(self) -> bool:
        return self._is_on

    async def async_turn_on(self, **kwargs) -> None:
        await self.coordinator.client.set_led(True)
        self._is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        await self.coordinator.client.set_led(False)
        self._is_on = False
        self.async_write_ha_state()
