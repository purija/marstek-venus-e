"""Switch entity for Marstek Venus LED panel (optional)."""
from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import CONF_ENABLE_LED, DEFAULT_ENABLE_CONTROLS, DOMAIN, UID_LED
from .coordinator import MarstekCoordinator
from .entity import MarstekControlEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    if not entry.options.get(CONF_ENABLE_LED, DEFAULT_ENABLE_CONTROLS):
        return
    coordinator: MarstekCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([MarstekLEDSwitch(coordinator)])


class MarstekLEDSwitch(MarstekControlEntity, SwitchEntity, RestoreEntity):
    """LED panel switch.

    The device API has no GET for the LED state, so the last state set from
    Home Assistant is restored after a restart (unknown until first use). It is
    only an assumption and is never re-sent to the device on restart.
    """

    _attr_name = "LED Panel"
    _attr_assumed_state = True
    _unique_suffix = UID_LED

    _is_on: bool | None = None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if (last := await self.async_get_last_state()) is not None:
            if last.state in (STATE_ON, "off"):
                self._is_on = last.state == STATE_ON

    @property
    def is_on(self) -> bool | None:
        return self._is_on

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._async_send(self.coordinator.client.set_led(True))
        self._is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._async_send(self.coordinator.client.set_led(False))
        self._is_on = False
        self.async_write_ha_state()
