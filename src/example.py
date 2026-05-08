#!/usr/bin/env python3
"""
Standalone test script for the Marstek Venus Open API.

Usage:
    python3 src/example.py <device-ip> [port]

Example:
    python3 src/example.py 192.168.1.232
    python3 src/example.py 192.168.1.232 49200
"""
from __future__ import annotations

import json
import socket
import sys
from typing import Any


class MarstekError(Exception):
    def __init__(self, message: str, code: int | None = None) -> None:
        super().__init__(message)
        self.code = code


class MarstekClient:
    """Synchronous UDP client — no dependencies beyond the Python stdlib."""

    def __init__(self, host: str, port: int = 30000, timeout: float = 5.0) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout
        self._req_id = 0

    def _next_id(self) -> int:
        self._req_id = (self._req_id + 1) % 65536
        return self._req_id

    def request(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = json.dumps({
            "id": self._next_id(),
            "method": method,
            "params": params if params is not None else {"id": 0},
        }).encode()
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.settimeout(self.timeout)
            sock.sendto(payload, (self.host, self.port))
            data, _ = sock.recvfrom(65535)
        resp = json.loads(data.decode())
        if "error" in resp:
            e = resp["error"]
            raise MarstekError(e.get("message", "error"), e.get("code"))
        return resp.get("result", {})

    def get_device(self) -> dict[str, Any]:
        return self.request("Marstek.GetDevice", {"ble_mac": "0"})

    def get_bat_status(self) -> dict[str, Any]:
        return self.request("Bat.GetStatus", {"id": 0})

    def get_es_status(self) -> dict[str, Any]:
        return self.request("ES.GetStatus", {"id": 0})

    def get_es_mode(self) -> dict[str, Any]:
        return self.request("ES.GetMode", {"id": 0})

    def get_em_status(self) -> dict[str, Any]:
        return self.request("EM.GetStatus", {"id": 0})

    def set_mode(self, mode: str) -> bool:
        cfg_map = {
            "Auto": ("auto_cfg", {"enable": 1}),
            "AI":   ("ai_cfg",   {"enable": 1}),
            "UPS":  ("ups_cfg",  {"enable": 1}),
        }
        config: dict[str, Any] = {"mode": mode}
        if mode in cfg_map:
            key, val = cfg_map[mode]
            config[key] = val
        result = self.request("ES.SetMode", {"id": 0, "config": config})
        return bool(result.get("set_result"))

    def set_passive_mode(self, power: int, cd_time: int = 300) -> bool:
        result = self.request("ES.SetMode", {
            "id": 0,
            "config": {"mode": "Passive", "passive_cfg": {"power": power, "cd_time": cd_time}},
        })
        return bool(result.get("set_result"))

    def set_dod(self, value: int) -> bool:
        result = self.request("DOD.SET", {"value": value})
        return bool(result.get("set_result"))

    def set_led(self, state: bool) -> bool:
        result = self.request("Led.Ctrl", {"state": 1 if state else 0})
        return bool(result.get("set_result"))


def _query(client: MarstekClient, label: str, fn, delay: float = 1.0):
    """Run a query, print result or warn on failure. Returns result dict or {}."""
    import time
    time.sleep(delay)
    try:
        return fn()
    except (MarstekError, OSError) as e:
        print(f"[WARN] {label}: {e}")
        return {}
    except socket.timeout:
        print(f"[WARN] {label}: timeout")
        return {}


def main(host: str, port: int) -> None:
    """
    Query order matters: the device processes requests sequentially and drops
    concurrent ones. We send them one at a time with a 1 s pause between.
    Bat.GetStatus is polled first since it conflicts with ES.GetStatus.
    """
    client = MarstekClient(host=host, port=port, timeout=10.0)
    print(f"Connecting to {host}:{port} …\n")

    # 1. Energy system — always reliable, must come first
    es = _query(client, "ES.GetStatus", client.get_es_status, delay=0)
    if es:
        print("=== Energy System ===")
        print(f"  Battery SOC        : {es.get('bat_soc')} %")
        print(f"  Battery capacity   : {es.get('bat_cap')} Wh")
        print(f"  Solar power        : {es.get('pv_power')} W")
        print(f"  Grid power         : {es.get('ongrid_power')} W  (- = export)")
        print(f"  Off-grid power     : {es.get('offgrid_power')} W")
        print(f"  Total solar energy : {es.get('total_pv_energy')} Wh")
        print(f"  Total grid export  : {es.get('total_grid_output_energy')} Wh")
        print(f"  Total grid import  : {es.get('total_grid_input_energy')} Wh")
        print(f"  Total load energy  : {es.get('total_load_energy')} Wh")
        print()

    # 3. Energy meter (CT clamp)
    em = _query(client, "EM.GetStatus", client.get_em_status)
    if em:
        print("=== Energy Meter (CT) ===")
        print(f"  CT connected   : {'Yes' if em.get('ct_state') else 'No'}")
        print(f"  Total power    : {em.get('total_power')} W")
        print(f"  Phase A/B/C    : {em.get('a_power')} / {em.get('b_power')} / {em.get('c_power')} W")
        print()

    # 4. Current mode
    mode = _query(client, "ES.GetMode", client.get_es_mode)
    if mode:
        print("=== Mode ===")
        print(f"  Mode           : {mode.get('mode')}")
        print(f"  CT connected   : {'Yes' if mode.get('ct_state') else 'No'}")
        print(f"  CT total power : {mode.get('total_power')} W")
        raw_in = mode.get("input_energy")
        raw_out = mode.get("output_energy")
        if raw_in is not None:
            print(f"  CT in energy   : {raw_in * 0.1:.1f} Wh")
        if raw_out is not None:
            print(f"  CT out energy  : {raw_out * 0.1:.1f} Wh")
        print()

    # 5. Battery — intermittent on firmware 148, place last so it doesn't block others
    bat = _query(client, "Bat.GetStatus", client.get_bat_status)
    if bat:
        print("=== Battery ===")
        print(f"  SOC              : {bat.get('soc')} %")
        print(f"  Temperature      : {bat.get('bat_temp')} °C")
        print(f"  Remaining cap.   : {bat.get('bat_capacity')} Wh")
        print(f"  Rated cap.       : {bat.get('rated_capacity')} Wh")
        print(f"  Charging allowed : {bat.get('charg_flag')}")
        print(f"  Discharge allowed: {bat.get('dischrg_flag')}")
        print()

    # Uncomment to test write commands:
    # import time; time.sleep(1)
    # print(f"Set Auto mode: {'OK' if client.set_mode('Auto') else 'FAILED'}")
    # time.sleep(1)
    # print(f"Set DOD 80 %:  {'OK' if client.set_dod(80) else 'FAILED'}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    _host = sys.argv[1]
    _port = int(sys.argv[2]) if len(sys.argv) > 2 else 30000
    main(_host, _port)
