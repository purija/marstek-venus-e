"""Async UDP client for the Marstek Venus Open API."""
from __future__ import annotations

import asyncio
import json
import logging
import socket
from typing import Any

_LOGGER = logging.getLogger(__name__)


class MarstekError(Exception):
    def __init__(self, message: str, code: int | None = None) -> None:
        super().__init__(message)
        self.code = code


class MarstekClient:
    """UDP client for the Marstek Venus Open API (JSON-RPC over UDP)."""

    def __init__(self, host: str, port: int = 30000, timeout: float = 5.0) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout
        self._request_id = 0

    def _next_id(self) -> int:
        self._request_id = (self._request_id + 1) % 65536
        return self._request_id

    def _send_sync(self, payload: bytes) -> dict[str, Any]:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.settimeout(self.timeout)
            sock.sendto(payload, (self.host, self.port))
            data, _ = sock.recvfrom(65535)
        return json.loads(data.decode())

    async def _send(self, payload: bytes) -> dict[str, Any]:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._send_sync, payload)

    async def request(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Send a command and return the result dict, or raise MarstekError."""
        payload = json.dumps({
            "id": self._next_id(),
            "method": method,
            "params": params if params is not None else {"id": 0},
        }).encode()
        response = await self._send(payload)
        if "error" in response:
            err = response["error"]
            raise MarstekError(err.get("message", "Unknown error"), err.get("code"))
        return response.get("result", {})

    # ── Query methods ──────────────────────────────────────────────────────────

    async def get_device(self) -> dict[str, Any]:
        """Discover device and get basic info. Use ble_mac='0' as wildcard."""
        return await self.request("Marstek.GetDevice", {"ble_mac": "0"})

    async def get_bat_status(self) -> dict[str, Any]:
        """Battery SOC, temperature, remaining & rated capacity, charge flags."""
        return await self.request("Bat.GetStatus", {"id": 0})

    async def get_es_status(self) -> dict[str, Any]:
        """Energy system: power flows and cumulative energy totals."""
        return await self.request("ES.GetStatus", {"id": 0})

    async def get_es_mode(self) -> dict[str, Any]:
        """Current operating mode, CT power per phase, CT cumulative energy."""
        return await self.request("ES.GetMode", {"id": 0})

    async def get_em_status(self) -> dict[str, Any]:
        """Energy meter / CT status and measurements."""
        return await self.request("EM.GetStatus", {"id": 0})

    async def get_wifi_status(self) -> dict[str, Any]:
        """WiFi connection info (IP, SSID, RSSI, gateway)."""
        return await self.request("Wifi.GetStatus", {"id": 0})

    # ── Command methods ────────────────────────────────────────────────────────

    async def set_mode(self, mode: str) -> bool:
        """Set operating mode to Auto, AI, or UPS."""
        cfg_map = {
            "Auto": ("auto_cfg", {"enable": 1}),
            "AI": ("ai_cfg", {"enable": 1}),
            "UPS": ("ups_cfg", {"enable": 1}),
        }
        config: dict[str, Any] = {"mode": mode}
        if mode in cfg_map:
            key, val = cfg_map[mode]
            config[key] = val
        result = await self.request("ES.SetMode", {"id": 0, "config": config})
        return bool(result.get("set_result"))

    async def set_passive_mode(self, power: int, cd_time: int = 300) -> bool:
        """Set Passive mode with target power [W] and countdown [s]."""
        result = await self.request("ES.SetMode", {
            "id": 0,
            "config": {
                "mode": "Passive",
                "passive_cfg": {"power": power, "cd_time": cd_time},
            },
        })
        return bool(result.get("set_result"))

    async def set_manual_mode(
        self,
        time_num: int,
        start_time: str,
        end_time: str,
        power: int,
        week_set: int = 127,
        enable: int = 1,
    ) -> bool:
        """Set Manual mode time-slot. week_set is a bitmask Mon=bit0 … Sun=bit6."""
        result = await self.request("ES.SetMode", {
            "id": 0,
            "config": {
                "mode": "Manual",
                "manual_cfg": {
                    "time_num": time_num,
                    "start_time": start_time,
                    "end_time": end_time,
                    "week_set": week_set,
                    "power": power,
                    "enable": enable,
                },
            },
        })
        return bool(result.get("set_result"))

    async def set_dod(self, value: int) -> bool:
        """Set depth of discharge. Range: 30–88 (default 88)."""
        result = await self.request("DOD.SET", {"value": value})
        return bool(result.get("set_result"))

    async def set_led(self, state: bool) -> bool:
        """Turn the LED panel on (True) or off (False)."""
        result = await self.request("Led.Ctrl", {"state": 1 if state else 0})
        return bool(result.get("set_result"))

    async def set_ble_advertising(self, enable: bool) -> bool:
        """Enable (True) or disable (False) Bluetooth advertising.
        Note: API polarity is inverted — enable=0 means start advertising."""
        result = await self.request("Ble.Adv", {"enable": 0 if enable else 1})
        return bool(result.get("set_result"))
