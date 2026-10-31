"""Shared base for the optional Marstek Venus control entities."""
from __future__ import annotations

from collections.abc import Awaitable

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .client import MarstekError
from .coordinator import MarstekCoordinator

# JSON-RPC "Method not found": the device does not know the command.
METHOD_NOT_FOUND = -32601


class MarstekControlEntity(CoordinatorEntity[MarstekCoordinator]):
    """Base class for entities that write to the device."""

    _attr_has_entity_name = True
    _unique_suffix: str

    def __init__(self, coordinator: MarstekCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry_id}_{self._unique_suffix}"
        self._attr_device_info = coordinator.device_info

    async def _async_send(self, command: Awaitable[None]) -> None:
        """Await a client command and surface failures in the UI."""
        try:
            await command
        except MarstekError as err:
            if err.code == METHOD_NOT_FOUND:
                raise HomeAssistantError(
                    f"{self.name}: not supported by this device or firmware "
                    "(DOD, LED and Bluetooth need firmware 150 or newer on Venus C/E)"
                ) from err
            raise HomeAssistantError(f"{self.name}: command failed ({err})") from err
        except OSError as err:
            raise HomeAssistantError(f"{self.name}: command failed ({err})") from err
