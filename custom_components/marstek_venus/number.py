"""Number entity for Marstek Venus depth of discharge (DOD, optional)."""
from __future__ import annotations

from homeassistant.components.number import NumberMode, RestoreNumber
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_ENABLE_DOD, DEFAULT_ENABLE_CONTROLS, DOMAIN, UID_DOD
from .coordinator import MarstekCoordinator
from .entity import MarstekControlEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    if not entry.options.get(CONF_ENABLE_DOD, DEFAULT_ENABLE_CONTROLS):
        return
    coordinator: MarstekCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([MarstekDODNumber(coordinator)])


class MarstekDODNumber(MarstekControlEntity, RestoreNumber):
    """Depth of discharge setting (30–88 %).

    The device API has no GET for DOD, so the last value set from Home
    Assistant is restored from the entity state after a restart. It is only an
    assumption: a change made in the Marstek app is not visible here. The value
    is never re-sent to the device on restart.
    """

    _attr_name = "Depth of Discharge"
    _attr_native_min_value = 30
    _attr_native_max_value = 88
    _attr_native_step = 1
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_mode = NumberMode.BOX
    _attr_assumed_state = True
    _unique_suffix = UID_DOD

    _value: int | None = None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if (last := await self.async_get_last_number_data()) and last.native_value is not None:
            self._value = int(last.native_value)

    @property
    def native_value(self) -> int | None:
        return self._value

    async def async_set_native_value(self, value: float) -> None:
        int_value = int(value)
        await self._async_send(self.coordinator.client.set_dod(int_value))
        self._value = int_value
        self.async_write_ha_state()
