#!/usr/bin/env python3
"""
Read-only probe for the Marstek Venus Open API (Rev 3.1 migration, step 1).

Sends only GET-style queries (one at a time, 1 s apart) and records for every
method whether the device answers, with what, or with which error code. The
result clarifies the open questions in docs/api-rev3-1-migration.md (Q1-Q5).

Usage:
    python3 src/probe.py <device-ip> [port] [--timeout 10] [--out FILE]
    python3 src/probe.py <device-ip> --check-dod 80   # optional, writes!

--check-dod N sends DOD.SET with value N. Pass the value that is *currently*
set in the Marstek app, so the device state does not change. It answers the
question whether the SYS component (DOD/LED/BLE) exists on this firmware
(error -32601 "Method not found" = not available).

Identifiers (MACs, IPs, SSID) are masked in the console output and in the file.
"""
from __future__ import annotations

import argparse
import json
import socket
import sys
import time
from pathlib import Path
from typing import Any

GAP = 1.0  # the firmware drops requests that arrive while it is busy

QUERIES: list[tuple[str, dict[str, Any]]] = [
    ("Marstek.GetDevice", {"ble_mac": "0"}),
    ("ES.GetStatus", {"id": 0}),
    ("ES.GetMode", {"id": 0}),
    ("EM.GetStatus", {"id": 0}),
    ("Bat.GetStatus", {"id": 0}),
    ("PV.GetStatus", {"id": 0}),      # Rev 3.1: only Venus A/D
    ("Wifi.GetStatus", {"id": 0}),
    ("BLE.GetStatus", {"id": 0}),
]

_MASK_KEYS = {"ble_mac", "wifi_mac", "wifi_name", "ssid", "ip", "sta_ip", "sta_gate", "sta_mask", "sta_dns", "src"}


def call(host: str, port: int, timeout: float, req_id: int, method: str, params: dict) -> dict[str, Any]:
    payload = json.dumps({"id": req_id, "method": method, "params": params}).encode()
    started = time.monotonic()
    out: dict[str, Any] = {"method": method}
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.settimeout(timeout)
            sock.sendto(payload, (host, port))
            data, _ = sock.recvfrom(65535)
        resp = json.loads(data.decode())
        if "error" in resp:
            out["status"] = "error"
            out["error"] = resp["error"]
        else:
            out["status"] = "ok"
            out["result"] = resp.get("result", {})
        out["src"] = resp.get("src")
    except (TimeoutError, socket.timeout):
        out["status"] = "timeout"
    except (OSError, ValueError) as err:
        out["status"] = "failed"
        out["error"] = str(err)
    out["seconds"] = round(time.monotonic() - started, 2)
    return out


def mask(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: ("***" if k in _MASK_KEYS and v else mask(v)) for k, v in value.items()}
    return value


def findings(by_method: dict[str, dict[str, Any]]) -> list[str]:
    """Answers to the open questions, as far as the probe data allows."""
    lines: list[str] = []

    dev = by_method.get("Marstek.GetDevice", {})
    if dev.get("status") == "ok":
        r = dev["result"]
        lines.append(f"Q2 device={r.get('device')!r}  ver={r.get('ver')!r}  (ver >= 150 => SYS available per Rev 3.1)")
    else:
        lines.append(f"Q2 Marstek.GetDevice: {dev.get('status')} - unicast may be rejected; use ES.GetStatus as reachability check")

    es = by_method.get("ES.GetStatus", {})
    if es.get("status") == "ok":
        lines.append(f"Q1 total_pv_energy raw={es['result'].get('total_pv_energy')!r}  "
                     "(Rev 2: Wh, Rev 3.1: 0.01 kWh = 10 Wh per unit; compare with the app once the value is > 0)")

    mode = by_method.get("ES.GetMode", {})
    if mode.get("status") == "ok":
        lines.append(f"Q3 ES.GetMode mode={mode['result'].get('mode')!r}  "
                     "(set UPS in the app once and re-run to see whether it reports 'UPS' or 'Ups')")

    pv = by_method.get("PV.GetStatus", {})
    code = (pv.get("error") or {}).get("code") if isinstance(pv.get("error"), dict) else None
    if pv.get("status") == "ok":
        lines.append(f"Q4 PV.GetStatus answers, keys={sorted(pv['result'])}")
    else:
        lines.append(f"Q4 PV.GetStatus: {pv.get('status')} code={code} (expected on Venus C/E: -32601)")

    em = by_method.get("EM.GetStatus", {})
    if mode.get("status") == "ok" and em.get("status") == "ok":
        keys = ("ct_state", "total_power", "a_power", "b_power", "c_power")
        same = all(mode["result"].get(k) == em["result"].get(k) for k in keys)
        lines.append(f"Q6 CT data ES.GetMode vs EM.GetStatus identical={same} (mode={mode['result'].get('mode')!r}); "
                     "repeat in Manual/Passive/UPS: does EM still report valid CT values there?")
    else:
        lines.append("Q6 not comparable (ES.GetMode or EM.GetStatus unavailable)")

    dod = by_method.get("DOD.SET")
    if dod:
        dcode = (dod.get("error") or {}).get("code") if isinstance(dod.get("error"), dict) else None
        verdict = {"ok": "SYS available", "error": f"error {dcode} ({'SYS NOT available' if dcode == -32601 else 'see message'})"}
        lines.append(f"Q5 DOD.SET: {verdict.get(dod['status'], dod['status'])}")
    else:
        lines.append("Q5 DOD.SET not tested (use --check-dod N)")
    return lines


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("host")
    ap.add_argument("port", nargs="?", type=int, default=30000)
    ap.add_argument("--timeout", type=float, default=10.0)
    ap.add_argument("--out", type=Path, default=None, help="result file (default: output/probe-<time>.json)")
    ap.add_argument("--check-dod", type=int, metavar="N", help="also send DOD.SET N (writes!), N in 30-88")
    args = ap.parse_args()

    if args.check_dod is not None and not 30 <= args.check_dod <= 88:
        ap.error("--check-dod must be between 30 and 88")

    calls = list(QUERIES)
    if args.check_dod is not None:
        calls.append(("DOD.SET", {"value": args.check_dod}))

    results: list[dict[str, Any]] = []
    for i, (method, params) in enumerate(calls, start=1):
        if i > 1:
            time.sleep(GAP)
        res = call(args.host, args.port, args.timeout, i, method, params)
        results.append(res)
        detail = res.get("error") or ""
        print(f"{method:<20} {res['status']:<8} {res['seconds']:>5}s  {mask(detail) if detail else ''}")

    by_method = {r["method"]: r for r in results}
    print("\nFindings:")
    for line in findings(by_method):
        print("  " + line)

    out = args.out or Path("output") / f"probe-{time.strftime('%Y%m%d-%H%M%S')}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    masked = [{**r, "result": mask(r["result"]), "src": "***" if r.get("src") else None} if "result" in r
              else {**r, "src": "***" if r.get("src") else None} for r in results]
    out.write_text(json.dumps({"spec": "rev3-1", "results": masked}, indent=2, ensure_ascii=False))
    print(f"\nSaved (identifiers masked): {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
