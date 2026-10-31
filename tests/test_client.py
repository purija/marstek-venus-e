"""MarstekClient against a simulated UDP device."""
from __future__ import annotations

import asyncio
import json

import pytest

from custom_components.marstek_venus import client as client_mod
from custom_components.marstek_venus.client import MarstekClient, MarstekError


class FakeDevice(asyncio.DatagramProtocol):
    """Minimal UDP server: answers each request with the next queued reply.

    A reply of None means "stay silent" (client runs into a timeout). Without a
    queued reply the device confirms with ``set_result: true``.
    """

    def __init__(self) -> None:
        self.requests: list[dict] = []
        self.replies: list[dict | None] = []
        self.port = 0
        self._transport: asyncio.DatagramTransport | None = None

    def connection_made(self, transport) -> None:
        self._transport = transport

    def datagram_received(self, data: bytes, addr) -> None:
        request = json.loads(data)
        self.requests.append(request)
        reply = self.replies.pop(0) if self.replies else {"result": {"set_result": True}}
        if reply is not None:
            self._transport.sendto(json.dumps({"id": request["id"], **reply}).encode(), addr)


@pytest.fixture
async def device(socket_enabled):
    """Fake device on a free localhost port. The client runs its blocking socket
    call in an executor thread, so the event loop stays free to answer."""
    loop = asyncio.get_running_loop()
    dev = FakeDevice()
    transport, _ = await loop.create_datagram_endpoint(
        lambda: dev, local_addr=("127.0.0.1", 0)
    )
    dev.port = transport.get_extra_info("sockname")[1]
    yield dev
    transport.close()


@pytest.fixture
def client(device, monkeypatch):
    monkeypatch.setattr(client_mod, "MIN_REQUEST_GAP", 0.0)
    return MarstekClient("127.0.0.1", device.port, timeout=0.5)


async def test_request_returns_result(device, client):
    device.replies.append({"result": {"bat_soc": 55}})
    assert await client.get_es_status() == {"bat_soc": 55}
    assert device.requests[0]["method"] == "ES.GetStatus"
    assert device.requests[0]["params"] == {"id": 0}


async def test_error_response_raises_with_code(device, client):
    device.replies.append({"error": {"code": -32601, "message": "Method not found"}})
    with pytest.raises(MarstekError) as exc:
        await client.get_em_status()
    assert exc.value.code == -32601


async def test_command_rejected_raises(device, client):
    device.replies.append({"result": {"set_result": False}})
    with pytest.raises(MarstekError):
        await client.set_dod(60)


async def test_command_retries_once_on_timeout(device, client):
    device.replies.extend([None, {"result": {"set_result": True}}])
    await client.set_dod(60)
    assert len(device.requests) == 2


async def test_command_gives_up_after_one_retry(device, client):
    device.replies.extend([None, None])
    with pytest.raises(OSError):
        await client.set_dod(60)
    assert len(device.requests) == 2


async def test_concurrent_requests_are_serialised_with_gap(device, monkeypatch):
    """Two requests issued at once reach the device one after the other, >= gap apart."""
    monkeypatch.setattr(client_mod, "MIN_REQUEST_GAP", 0.3)
    c = MarstekClient("127.0.0.1", device.port, timeout=0.5)
    loop = asyncio.get_running_loop()
    start = loop.time()
    await asyncio.gather(c.get_es_status(), c.get_em_status())
    assert loop.time() - start >= 0.25
    assert sorted(r["method"] for r in device.requests) == ["EM.GetStatus", "ES.GetStatus"]


async def test_set_mode_rejects_modes_with_parameters(client):
    with pytest.raises(ValueError):
        await client.set_mode("Manual")


async def test_set_mode_ups_payload(device, client):
    await client.set_mode("UPS")
    assert device.requests[0]["params"]["config"] == {"mode": "UPS", "ups_cfg": {"enable": 1}}


async def test_ble_polarity_is_inverted(device, client):
    await client.set_ble_advertising(True)
    await client.set_ble_advertising(False)
    assert [r["params"]["enable"] for r in device.requests] == [0, 1]


# ── Rev 3.1: set_manual_mode ──────────────────────────────────────────────────

SLOT = dict(start_time="08:00", end_time="10:00", power=500)


async def test_manual_mode_without_manual_set_keeps_old_payload(device, client):
    await client.set_manual_mode(time_num=9, **SLOT)
    cfg = device.requests[0]["params"]["config"]["manual_cfg"]
    assert "manual_set" not in cfg
    assert cfg["time_num"] == 9


async def test_manual_mode_sends_manual_set_for_e_mini(device, client):
    await client.set_manual_mode(time_num=5, manual_set=2, **SLOT)
    cfg = device.requests[0]["params"]["config"]["manual_cfg"]
    assert cfg["manual_set"] == 2


@pytest.mark.parametrize("time_num", [-1, 10])
async def test_manual_mode_rejects_invalid_time_num(device, client, time_num):
    with pytest.raises(ValueError):
        await client.set_manual_mode(time_num=time_num, **SLOT)
    assert device.requests == []


async def test_manual_mode_e_mini_limit_is_five(device, client):
    with pytest.raises(ValueError):
        await client.set_manual_mode(time_num=6, manual_set=1, **SLOT)
    assert device.requests == []


async def test_manual_mode_rejects_invalid_manual_set(device, client):
    with pytest.raises(ValueError):
        await client.set_manual_mode(time_num=0, manual_set=4, **SLOT)
    assert device.requests == []
