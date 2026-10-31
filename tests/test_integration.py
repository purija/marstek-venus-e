"""Integration tests: config flow, sensors, controls (client is mocked)."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.marstek_venus.client import MarstekError
from custom_components.marstek_venus.const import (
    CONF_ENABLE_DOD,
    CONF_ENABLE_MODE,
    DOMAIN,
)

ES_STATUS = {"bat_soc": 61, "total_pv_energy": 0, "total_grid_input_energy": 1234}
EM_STATUS = {"ct_state": 1, "a_power": -231, "b_power": -46, "c_power": 274, "total_power": -2,
             "input_energy": 1000, "output_energy": 250}
ES_MODE = {"mode": "Auto"}
BAT_STATUS = {"bat_temp": 21.5}

@pytest.fixture(autouse=True)
def _enable_custom_integrations(enable_custom_integrations):
    """Let Home Assistant load custom_components/ in every test of this module."""


CLIENT = "custom_components.marstek_venus.coordinator.MarstekClient"
CONFIG_FLOW_CLIENT = "custom_components.marstek_venus.config_flow.MarstekClient"


def _fake_client(es_mode=None, **overrides) -> AsyncMock:
    client = AsyncMock()
    client.get_es_status.return_value = ES_STATUS
    client.get_em_status.return_value = EM_STATUS
    client.get_es_mode.return_value = es_mode or ES_MODE
    client.get_bat_status.return_value = BAT_STATUS
    for name, value in overrides.items():
        setattr(client, name, value)
    return client


def _entry(options=None, **data) -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        title="Venus E",
        data={"host": "192.0.2.1", "port": 30000, "device_name": "VenusE 3.0",
              "ble_mac": "aabbccddeeff", **data},
        options=options or {},
    )


async def _setup(hass: HomeAssistant, entry: MockConfigEntry, client: AsyncMock) -> None:
    entry.add_to_hass(hass)
    with patch(CLIENT, return_value=client):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()


# ── Config flow ───────────────────────────────────────────────────────────────

async def _run_flow(hass: HomeAssistant, client: AsyncMock):
    with patch(CONFIG_FLOW_CLIENT, return_value=client), \
         patch("custom_components.marstek_venus.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
        return await hass.config_entries.flow.async_configure(
            result["flow_id"], {"host": "192.0.2.1", "port": 30000}
        )


async def test_config_flow_stores_ver(hass: HomeAssistant) -> None:
    client = _fake_client(get_device=AsyncMock(return_value={
        "device": "VenusE 3.0", "ble_mac": "aabbccddeeff", "ver": 148}))
    result = await _run_flow(hass, client)
    assert result["type"] == "create_entry"
    assert result["data"]["ver"] == 148
    assert result["data"]["ble_mac"] == "aabbccddeeff"


async def test_config_flow_without_discovery_still_creates_entry(hass: HomeAssistant) -> None:
    """Unicast Marstek.GetDevice may fail with a parse error: no ver, setup still works."""
    client = _fake_client(get_device=AsyncMock(side_effect=MarstekError("Parse error", -32700)))
    result = await _run_flow(hass, client)
    assert result["type"] == "create_entry"
    assert result["data"]["ver"] is None
    assert result["result"].unique_id == "192.0.2.1"


async def test_config_flow_cannot_connect(hass: HomeAssistant) -> None:
    client = _fake_client(get_es_status=AsyncMock(side_effect=MarstekError("nope", -1)))
    result = await _run_flow(hass, client)
    assert result["type"] == "form"
    assert result["errors"] == {"base": "cannot_connect"}


# ── Device info ───────────────────────────────────────────────────────────────

def _device(hass: HomeAssistant, entry: MockConfigEntry):
    return dr.async_get(hass).async_get_device_by_identifier(
        (DOMAIN, "aabbccddeeff"), entry.entry_id
    )


async def test_sw_version_from_ver(hass: HomeAssistant) -> None:
    entry = _entry(ver=148)
    await _setup(hass, entry, _fake_client())
    assert _device(hass, entry).sw_version == "148"


async def test_entry_without_ver_starts(hass: HomeAssistant) -> None:
    """Entries created before Rev 3.1 support have no 'ver' key at all."""
    entry = _entry()
    assert "ver" not in entry.data
    await _setup(hass, entry, _fake_client())
    assert _device(hass, entry).sw_version is None


# ── Sensors ───────────────────────────────────────────────────────────────────

async def test_ct_sensors_read_from_em_status(hass: HomeAssistant) -> None:
    await _setup(hass, _entry(), _fake_client())
    assert hass.states.get("sensor.venus_e_ct_total_power").state == "-2"
    # raw 1000 x 0.1 = 100 Wh
    assert float(hass.states.get("sensor.venus_e_ct_input_energy").state) == pytest.approx(100.0)


async def test_total_pv_energy_disabled_by_default(hass: HomeAssistant) -> None:
    await _setup(hass, _entry(), _fake_client())
    assert hass.states.get("sensor.venus_e_total_solar_energy") is None
    # the other cumulative energy counters stay enabled and unscaled
    assert hass.states.get("sensor.venus_e_total_grid_input_energy").state == "1234"


# ── Controls ──────────────────────────────────────────────────────────────────

async def test_controls_off_by_default(hass: HomeAssistant) -> None:
    await _setup(hass, _entry(), _fake_client())
    assert hass.states.get("select.venus_e_operating_mode") is None
    assert hass.states.get("number.venus_e_depth_of_discharge") is None


@pytest.mark.parametrize("device_mode", ["UPS", "Ups", "ups"])
async def test_mode_select_is_case_insensitive(hass: HomeAssistant, device_mode: str) -> None:
    await _setup(hass, _entry({CONF_ENABLE_MODE: True}), _fake_client(es_mode={"mode": device_mode}))
    assert hass.states.get("select.venus_e_operating_mode").state == "UPS"


async def test_mode_select_unknown_for_manual(hass: HomeAssistant) -> None:
    await _setup(hass, _entry({CONF_ENABLE_MODE: True}), _fake_client(es_mode={"mode": "Manual"}))
    assert hass.states.get("select.venus_e_operating_mode").state == "unknown"


async def test_method_not_found_gives_clear_message(hass: HomeAssistant) -> None:
    client = _fake_client(set_dod=AsyncMock(side_effect=MarstekError("Method not found", -32601)))
    await _setup(hass, _entry({CONF_ENABLE_DOD: True}), client)
    with pytest.raises(HomeAssistantError, match="not supported by this device or firmware"):
        await hass.services.async_call(
            "number", "set_value",
            {"entity_id": "number.venus_e_depth_of_discharge", "value": 60}, blocking=True)


async def test_other_errors_keep_generic_message(hass: HomeAssistant) -> None:
    client = _fake_client(set_dod=AsyncMock(side_effect=MarstekError("boom", -32000)))
    await _setup(hass, _entry({CONF_ENABLE_DOD: True}), client)
    with pytest.raises(HomeAssistantError, match="command failed"):
        await hass.services.async_call(
            "number", "set_value",
            {"entity_id": "number.venus_e_depth_of_discharge", "value": 60}, blocking=True)
