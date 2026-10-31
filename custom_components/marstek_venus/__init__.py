"""Marstek Venus Home Assistant integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import CONTROLS, DEFAULT_ENABLE_CONTROLS, DOMAIN
from .coordinator import MarstekCoordinator

# Select / number / switch only create their entity when the matching control
# is enabled in the options (see const.CONTROLS).
PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.SELECT,
    Platform.NUMBER,
    Platform.SWITCH,
]


def _remove_disabled_controls(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Drop registry entries of controls that are switched off."""
    registry = er.async_get(hass)
    for option, (domain, suffix) in CONTROLS.items():
        if entry.options.get(option, DEFAULT_ENABLE_CONTROLS):
            continue
        entity_id = registry.async_get_entity_id(domain, DOMAIN, f"{entry.entry_id}_{suffix}")
        if entity_id:
            registry.async_remove(entity_id)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    coordinator = MarstekCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    _remove_disabled_controls(hass, entry)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


async def _async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload integration when options change (polling, timeout, controls)."""
    await hass.config_entries.async_reload(entry.entry_id)
