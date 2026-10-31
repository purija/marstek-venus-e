"""Integration tests: config flow, sensors, controls (client is mocked)."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.marstek_venus.client import MarstekError
from custom_components.marstek_venus.const import (
    CONF_ENABLE_DOD,
    CONF_ENABLE_LED,
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


# ── Migration of installations from before the opt-in controls ───────────────

def _preregister(hass: HomeAssistant, entry: MockConfigEntry, domain: str, suffix: str, object_id: str):
    """Create a registry entry like an older version of the integration did."""
    return er.async_get(hass).async_get_or_create(
        domain, DOMAIN, f"{entry.entry_id}_{suffix}",
        config_entry=entry, suggested_object_id=object_id,
    )


async def test_legacy_entry_keeps_existing_controls(hass: HomeAssistant) -> None:
    """No enable_* options, but the entities exist: they must survive the update."""
    entry = _entry()
    entry.add_to_hass(hass)
    sel = _preregister(hass, entry, "select", "operating_mode", "venus_e_operating_mode")
    num = _preregister(hass, entry, "number", "dod", "venus_e_depth_of_discharge")
    sw = _preregister(hass, entry, "switch", "led", "venus_e_led_panel")
    await _setup(hass, entry, _fake_client())

    assert entry.options[CONF_ENABLE_MODE] is True
    assert entry.options[CONF_ENABLE_DOD] is True
    assert entry.options[CONF_ENABLE_LED] is True
    registry = er.async_get(hass)
    for ent in (sel, num, sw):
        assert registry.async_get(ent.entity_id) is not None   # same entity_id kept
        assert hass.states.get(ent.entity_id) is not None


async def test_legacy_migration_only_touches_controls_with_entries(hass: HomeAssistant) -> None:
    entry = _entry()
    entry.add_to_hass(hass)
    _preregister(hass, entry, "number", "dod", "venus_e_depth_of_discharge")
    await _setup(hass, entry, _fake_client())

    assert entry.options == {CONF_ENABLE_DOD: True}
    assert hass.states.get("select.venus_e_operating_mode") is None
    assert hass.states.get("switch.venus_e_led_panel") is None


async def test_control_switched_off_is_not_resurrected(hass: HomeAssistant) -> None:
    """An explicit False beats a leftover registry entry and removes it."""
    entry = _entry({CONF_ENABLE_MODE: False})
    entry.add_to_hass(hass)
    sel = _preregister(hass, entry, "select", "operating_mode", "venus_e_operating_mode")
    await _setup(hass, entry, _fake_client())

    assert entry.options[CONF_ENABLE_MODE] is False
    assert er.async_get(hass).async_get(sel.entity_id) is None


async def test_new_installation_has_no_controls_and_no_options(hass: HomeAssistant) -> None:
    entry = _entry()
    await _setup(hass, entry, _fake_client())
    assert entry.options == {}


async def test_migration_does_not_reload_the_entry(hass: HomeAssistant) -> None:
    entry = _entry()
    entry.add_to_hass(hass)
    _preregister(hass, entry, "number", "dod", "venus_e_depth_of_discharge")
    client = _fake_client()
    await _setup(hass, entry, client)
    # one setup = one first refresh = one ES.GetStatus; a reload would poll again
    assert client.get_es_status.await_count == 1


async def test_legacy_dod_and_led_options_are_shown(hass: HomeAssistant) -> None:
    """Old versions kept the last value in options; show it until the entity has a state."""
    entry = _entry({CONF_ENABLE_DOD: True, CONF_ENABLE_LED: True, "dod": 70, "led": True})
    await _setup(hass, entry, _fake_client())
    assert hass.states.get("number.venus_e_depth_of_discharge").state == "70"
    assert hass.states.get("switch.venus_e_led_panel").state == "on"


async def test_dod_value_is_shown_after_set(hass: HomeAssistant) -> None:
    client = _fake_client(set_dod=AsyncMock())
    await _setup(hass, _entry({CONF_ENABLE_DOD: True}), client)
    await hass.services.async_call(
        "number", "set_value",
        {"entity_id": "number.venus_e_depth_of_discharge", "value": 55}, blocking=True)
    client.set_dod.assert_awaited_once_with(55)
    assert hass.states.get("number.venus_e_depth_of_discharge").state == "55"


@pytest.mark.parametrize(("service", "expected", "state"),
                         [("turn_on", True, "on"), ("turn_off", False, "off")])
async def test_led_switch(hass: HomeAssistant, service: str, expected: bool, state: str) -> None:
    client = _fake_client(set_led=AsyncMock())
    await _setup(hass, _entry({CONF_ENABLE_LED: True}), client)
    await hass.services.async_call(
        "switch", service, {"entity_id": "switch.venus_e_led_panel"}, blocking=True)
    client.set_led.assert_awaited_once_with(expected)
    assert hass.states.get("switch.venus_e_led_panel").state == state


# ── Polling: which endpoints are queried ──────────────────────────────────────

async def test_es_mode_not_polled_without_mode_control(hass: HomeAssistant) -> None:
    client = _fake_client()
    await _setup(hass, _entry(), client)
    client.get_es_status.assert_awaited_once()
    client.get_em_status.assert_awaited_once()
    client.get_bat_status.assert_awaited_once()
    client.get_es_mode.assert_not_awaited()


async def test_es_mode_polled_with_mode_control(hass: HomeAssistant) -> None:
    client = _fake_client()
    await _setup(hass, _entry({CONF_ENABLE_MODE: True}), client)
    client.get_es_mode.assert_awaited_once()


async def test_es_mode_still_polled_for_legacy_entry_with_select(hass: HomeAssistant) -> None:
    """The M1 migration must run before the coordinator decides what to poll."""
    entry = _entry()
    entry.add_to_hass(hass)
    _preregister(hass, entry, "select", "operating_mode", "venus_e_operating_mode")
    client = _fake_client(es_mode={"mode": "AI"})
    await _setup(hass, entry, client)
    client.get_es_mode.assert_awaited_once()
    assert hass.states.get("select.venus_e_operating_mode").state == "AI"


async def test_enabling_mode_control_starts_polling_es_mode(hass: HomeAssistant) -> None:
    client = _fake_client()
    entry = _entry()
    await _setup(hass, entry, client)
    client.get_es_mode.assert_not_awaited()
    with patch(CLIENT, return_value=client):
        hass.config_entries.async_update_entry(entry, options={CONF_ENABLE_MODE: True})
        await hass.async_block_till_done()
    client.get_es_mode.assert_awaited()
    assert hass.states.get("select.venus_e_operating_mode") is not None


# ── Coordinator failure handling ──────────────────────────────────────────────

async def test_partial_failure_keeps_last_value(hass: HomeAssistant) -> None:
    client = _fake_client()
    entry = _entry()
    await _setup(hass, entry, client)
    assert hass.states.get("sensor.venus_e_battery_temperature").state == "21.5"

    client.get_bat_status.side_effect = TimeoutError()
    coordinator = hass.data[DOMAIN][entry.entry_id]
    await coordinator.async_refresh()
    assert coordinator.last_update_success
    assert hass.states.get("sensor.venus_e_battery_temperature").state == "21.5"


async def test_total_failure_marks_entities_unavailable(hass: HomeAssistant) -> None:
    client = _fake_client()
    entry = _entry()
    await _setup(hass, entry, client)

    for name in ("get_es_status", "get_em_status", "get_bat_status"):
        getattr(client, name).side_effect = TimeoutError()
    coordinator = hass.data[DOMAIN][entry.entry_id]
    await coordinator.async_refresh()
    assert not coordinator.last_update_success
    assert hass.states.get("sensor.venus_e_battery_temperature").state == "unavailable"


async def test_mode_select_shows_new_mode_immediately(hass: HomeAssistant) -> None:
    client = _fake_client(set_mode=AsyncMock())
    await _setup(hass, _entry({CONF_ENABLE_MODE: True}), client)
    await hass.services.async_call(
        "select", "select_option",
        {"entity_id": "select.venus_e_operating_mode", "option": "UPS"}, blocking=True)
    client.set_mode.assert_awaited_once_with("UPS")
    assert hass.states.get("select.venus_e_operating_mode").state == "UPS"
