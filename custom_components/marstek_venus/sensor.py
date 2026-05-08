"""Sensor entities for Marstek Venus."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import MarstekCoordinator


@dataclass(frozen=True, kw_only=True)
class MarstekSensorEntityDescription(SensorEntityDescription):
    source: str = ""           # coordinator data key: es_status / es_mode / bat_status / em_status
    value_key: str = ""        # field name in that dict (defaults to .key)
    factor: float = 1.0        # multiply raw value by this before returning


SENSOR_DESCRIPTIONS: tuple[MarstekSensorEntityDescription, ...] = (
    # ── Battery ──────────────────────────────────────────────────────────────
    MarstekSensorEntityDescription(
        key="bat_soc",
        source="es_status",
        name="Battery State of Charge",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    MarstekSensorEntityDescription(
        key="bat_cap",
        source="es_status",
        name="Battery Available Capacity",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY_STORAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    MarstekSensorEntityDescription(
        key="bat_power",
        source="es_status",
        name="Battery Power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    MarstekSensorEntityDescription(
        key="bat_temp",
        source="bat_status",
        name="Battery Temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    MarstekSensorEntityDescription(
        key="rated_capacity",
        source="bat_status",
        name="Battery Rated Capacity",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY_STORAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    # ── Solar ─────────────────────────────────────────────────────────────────
    MarstekSensorEntityDescription(
        key="pv_power",
        source="es_status",
        name="Solar Power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # ── Grid & load ───────────────────────────────────────────────────────────
    MarstekSensorEntityDescription(
        key="ongrid_power",
        source="es_status",
        name="Grid Power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    MarstekSensorEntityDescription(
        key="offgrid_power",
        source="es_status",
        name="Off-grid Load Power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # ── Cumulative energy (ES.GetStatus — values are in Wh directly) ──────────
    MarstekSensorEntityDescription(
        key="total_pv_energy",
        source="es_status",
        name="Total Solar Energy",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    MarstekSensorEntityDescription(
        key="total_grid_output_energy",
        source="es_status",
        name="Total Grid Output Energy",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    MarstekSensorEntityDescription(
        key="total_grid_input_energy",
        source="es_status",
        name="Total Grid Input Energy",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    MarstekSensorEntityDescription(
        key="total_load_energy",
        source="es_status",
        name="Total Load Energy",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    # ── CT / Energy meter (ES.GetMode — energy values require ×0.1) ──────────
    MarstekSensorEntityDescription(
        key="ct_total_power",
        source="es_mode",
        value_key="total_power",
        name="CT Total Power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    MarstekSensorEntityDescription(
        key="ct_a_power",
        source="es_mode",
        value_key="a_power",
        name="CT Phase A Power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    MarstekSensorEntityDescription(
        key="ct_b_power",
        source="es_mode",
        value_key="b_power",
        name="CT Phase B Power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    MarstekSensorEntityDescription(
        key="ct_c_power",
        source="es_mode",
        value_key="c_power",
        name="CT Phase C Power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    # CT energies: raw value × 0.1 = Wh
    MarstekSensorEntityDescription(
        key="ct_input_energy",
        source="es_mode",
        value_key="input_energy",
        factor=0.1,
        name="CT Input Energy",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    MarstekSensorEntityDescription(
        key="ct_output_energy",
        source="es_mode",
        value_key="output_energy",
        factor=0.1,
        name="CT Output Energy",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: MarstekCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        MarstekSensorEntity(coordinator, desc) for desc in SENSOR_DESCRIPTIONS
    )


class MarstekSensorEntity(CoordinatorEntity[MarstekCoordinator], SensorEntity):
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: MarstekCoordinator,
        description: MarstekSensorEntityDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.entry_id}_{description.key}"
        self._attr_device_info = coordinator.device_info

    @property
    def native_value(self) -> float | int | None:
        desc: MarstekSensorEntityDescription = self.entity_description  # type: ignore[assignment]
        data = self.coordinator.data.get(desc.source, {})
        raw_key = desc.value_key or desc.key
        value = data.get(raw_key)
        if value is None:
            return None
        return value * desc.factor if desc.factor != 1.0 else value
