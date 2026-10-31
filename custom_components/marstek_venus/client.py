"""Async UDP client for the Marstek Venus Open API."""
from __future__ import annotations

import asyncio
import json
import logging
import socket
from typing import Any

_LOGGER = logging.getLogger(__name__)

# The firmware discards requests that arrive while it is still busy, so every
# request (poll or command) is serialised and spaced by at least this gap.
MIN_REQUEST_GAP = 1.0

# Commands set absolute values (no toggles), so repeating one after a lost
# datagram is safe.
COMMAND_RETRIES = 1

# Manual mode time slots (Open API Rev 3.1): 0-9, Venus E mini only 0-5.
MAX_TIME_NUM = 9
MAX_TIME_NUM_E_MINI = 5

# Modes that are enabled with a single "<name>_cfg": {"enable": 1} flag.
_SIMPLE_MODES = {"Auto": "auto_cfg", "AI": "ai_cfg", "UPS": "ups_cfg"}


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
        self._lock = asyncio.Lock()
        self._last_request_end = float("-inf")

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
        """Send a command and return the result dict, or raise MarstekError.

        Requests are processed one at a time with MIN_REQUEST_GAP between them,
        so a command issued from the UI never collides with a running poll.
        """
        payload = json.dumps({
            "id": self._next_id(),
            "method": method,
            "params": params if params is not None else {"id": 0},
        }).encode()
        loop = asyncio.get_running_loop()
        async with self._lock:
            gap = MIN_REQUEST_GAP - (loop.time() - self._last_request_end)
            if gap > 0:
                await asyncio.sleep(gap)
            try:
                response = await self._send(payload)
            finally:
                self._last_request_end = loop.time()
        if "error" in response:
            err = response["error"]
            raise MarstekError(err.get("message", "Unknown error"), err.get("code"))
        return response.get("result", {})

    async def _command(self, method: str, params: dict[str, Any]) -> None:
        """Send a write command, retrying once on timeout.

        Raises MarstekError if the device reports ``set_result: false``.
        """
        for attempt in range(COMMAND_RETRIES + 1):
            try:
                result = await self.request(method, params)
            except OSError:  # includes TimeoutError
                if attempt == COMMAND_RETRIES:
                    raise
                _LOGGER.debug("%s timed out, retrying", method)
                continue
            if not result.get("set_result"):
                raise MarstekError(f"{method} was rejected by the device")
            return

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

    async def set_mode(self, mode: str) -> None:
        """Set operating mode to Auto, AI, or UPS.

        Manual and Passive need extra parameters, use set_manual_mode() /
        set_passive_mode() for those.
        """
        if mode not in _SIMPLE_MODES:
            raise ValueError(f"Mode {mode!r} needs parameters, expected one of {list(_SIMPLE_MODES)}")
        await self._command("ES.SetMode", {
            "id": 0,
            "config": {"mode": mode, _SIMPLE_MODES[mode]: {"enable": 1}},
        })

    async def set_passive_mode(self, power: int, cd_time: int = 300) -> None:
        """Set Passive mode with target power [W] and countdown [s]."""
        await self._command("ES.SetMode", {
            "id": 0,
            "config": {
                "mode": "Passive",
                "passive_cfg": {"power": power, "cd_time": cd_time},
            },
        })

    async def set_manual_mode(
        self,
        time_num: int,
        start_time: str,
        end_time: str,
        power: int,
        week_set: int = 127,
        enable: int = 1,
        manual_set: int | None = None,
    ) -> None:
        """Set Manual mode time-slot. week_set is a bitmask Mon=bit0 … Sun=bit6.

        manual_set exists only on the Venus E mini (0 off, 1 charge, 2 discharge,
        3 auto). Passing it therefore also applies the E mini limit for time_num.
        """
        max_slot = MAX_TIME_NUM_E_MINI if manual_set is not None else MAX_TIME_NUM
        if not 0 <= time_num <= max_slot:
            raise ValueError(f"time_num must be 0-{max_slot}, got {time_num}")
        if manual_set is not None and manual_set not in range(4):
            raise ValueError(f"manual_set must be 0-3, got {manual_set}")
        manual_cfg: dict[str, Any] = {
            "time_num": time_num,
            "start_time": start_time,
            "end_time": end_time,
            "week_set": week_set,
            "power": power,
            "enable": enable,
        }
        if manual_set is not None:
            manual_cfg["manual_set"] = manual_set
        await self._command("ES.SetMode", {
            "id": 0,
            "config": {"mode": "Manual", "manual_cfg": manual_cfg},
        })

    async def set_dod(self, value: int) -> None:
        """Set depth of discharge. Range: 30–88 (default 88)."""
        await self._command("DOD.SET", {"value": value})

    async def set_led(self, state: bool) -> None:
        """Turn the LED panel on (True) or off (False)."""
        await self._command("Led.Ctrl", {"state": 1 if state else 0})

    async def set_ble_advertising(self, enable: bool) -> None:
        """Enable (True) or disable (False) Bluetooth advertising.
        Note: API polarity is inverted — enable=0 means start advertising."""
        await self._command("Ble.Adv", {"enable": 0 if enable else 1})
