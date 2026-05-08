# Marstek Venus — Home Assistant Integration

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![HA Version](https://img.shields.io/badge/Home%20Assistant-2023.x%2B-blue)](https://www.home-assistant.io/)

Local-network integration for the **Marstek Venus E / C / D** battery storage systems. Communicates directly with the device over **UDP** — no cloud, no Marstek account required after initial setup.

---

## Features

- **18 sensor entities**: battery SOC, power flows (solar, grid, off-grid, battery), cumulative energy, CT per-phase power
- **Operating mode select**: Auto / AI / Manual / Passive / UPS
- **Depth of Discharge (DOD)** number entity (30–88 %)
- **LED panel switch**
- Polling every 30 seconds, fully local
- Tested on: **Marstek Venus E 3.0** (firmware 148)

---

## Prerequisites

1. The Marstek device must be **connected to your home network** (WiFi or Ethernet).
2. Enable the **Open API** in the Marstek mobile app:
   - Open the app → select your device → Settings → **Open API**
   - Note the **UDP port** (default: **30000**)
3. Assign a **static IP** to the device in your router (recommended), or use the IP shown in the app.

---

## Installation

### Via HACS (recommended)

1. Open HACS in Home Assistant.
2. Go to **Integrations** → click the three-dot menu (⋮) → **Custom repositories**.
3. Add:
   - **Repository**: `https://github.com/YOUR_USERNAME/marstek-venus`
   - **Category**: Integration
4. Click **Add**.
5. Search for **Marstek Venus** in HACS and click **Download**.
6. **Restart Home Assistant**.

### Manual installation

1. Download or clone this repository.
2. Copy the `custom_components/marstek_venus/` folder into your HA configuration directory:
   ```
   config/
   └── custom_components/
       └── marstek_venus/   ← copy here
   ```
3. **Restart Home Assistant**.

---

## Configuration

1. Go to **Settings → Devices & Services → Add Integration**.
2. Search for **Marstek Venus**.
3. Enter:
   - **IP Address**: the device IP (e.g. `192.168.1.118`)
   - **UDP Port**: `30000` (or whatever you configured in the app)
4. Click **Submit** — the integration will connect and discover the device.

---

## Entities

### Sensors

| Entity | Unit | Notes |
|---|---|---|
| Battery State of Charge | % | |
| Battery Available Capacity | Wh | |
| Battery Temperature | °C | |
| Battery Power | W | positive = charging |
| Battery Rated Capacity | Wh | disabled by default |
| Solar Power | W | |
| Grid Power | W | negative = exporting |
| Off-grid Load Power | W | |
| Total Solar Energy | Wh | cumulative |
| Total Grid Output Energy | Wh | cumulative |
| Total Grid Input Energy | Wh | cumulative |
| Total Load Energy | Wh | cumulative |
| CT Total Power | W | requires CT clamp |
| CT Phase A / B / C Power | W | disabled by default |
| CT Input Energy | Wh | cumulative, ×0.1 factor |
| CT Output Energy | Wh | cumulative, ×0.1 factor |

### Controls

| Entity | Type | Notes |
|---|---|---|
| Operating Mode | Select | Auto / AI / Manual / Passive / UPS |
| Depth of Discharge | Number | 30–88 %, write-only (no GET in API) |
| LED Panel | Switch | write-only (no GET in API) |

---

## Energy Dashboard

The integration exposes the following sensors for use in the HA **Energy Dashboard**:

- **Solar production**: `Total Solar Energy`
- **Grid consumption**: `Total Grid Input Energy`
- **Grid return**: `Total Grid Output Energy`
- **Battery storage**: `Battery State of Charge` + `Battery Available Capacity`

---

## Known Limitations

| Issue | Details |
|---|---|
| `Bat.GetStatus` intermittent | On firmware 148 this endpoint occasionally times out. The sensor falls back to "unavailable" and recovers on the next poll. |
| `ES.GetMode` / `ES.GetMode` slow | Requires a 1 s pause after the previous request; the firmware processes commands sequentially. |
| DOD & LED state unknown after restart | The device API has no GET command for these — values are only tracked while HA is running. |
| Manual mode not exposed in select | Requires time-slot parameters. Use a HA automation with the `marstek_venus.set_manual_mode` service call (not yet implemented). |

---

## Tested Hardware

| Device | Firmware | Status |
|---|---|---|
| Marstek Venus E 3.0 | 148 | ✅ Working |
| Marstek Venus C | — | Should work (same API) |
| Marstek Venus D / A | — | Partial (no EM support per API docs) |

---

## Standalone Python Script

For testing without Home Assistant, a standalone script is included:

```bash
# Requires Python 3.10+
python3 src/example.py 192.168.1.118
python3 src/example.py 192.168.1.118 49200   # custom port
```

No dependencies beyond the Python standard library.

---

## API Reference

The device uses a JSON-RPC-style protocol over UDP. Full documentation is in [`input/MarstekDeviceOpenApi (1).pdf`](input/).

Quick reference:

```json
// Query battery status
{"id": 1, "method": "Bat.GetStatus", "params": {"id": 0}}

// Set operating mode
{"id": 2, "method": "ES.SetMode", "params": {"id": 0, "config": {"mode": "Auto", "auto_cfg": {"enable": 1}}}}

// Set depth of discharge
{"id": 3, "method": "DOD.SET", "params": {"value": 80}}
```

---

## License

MIT — see [LICENSE](LICENSE).

> **Disclaimer**: This integration is community-developed and not affiliated with or endorsed by Marstek. Use at your own risk. The Marstek Open API is provided "as is" for local use.
