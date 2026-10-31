# Marstek Venus — Home Assistant Integration

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![HA Version](https://img.shields.io/badge/Home%20Assistant-2023.x%2B-blue)](https://www.home-assistant.io/)
[![Buy me a coffee](https://img.shields.io/badge/Buy%20me%20a%20coffee-PayPal-0070BA?logo=paypal&logoColor=white)](https://www.paypal.com/paypalme/purija)

Local-network integration for the **Marstek Venus E / C / D** battery storage systems. Communicates directly with the device over **UDP** — no cloud, no Marstek account required after initial setup.

---

## Features

- **18 sensor entities**: battery SOC, power flows (solar, grid, off-grid, battery), cumulative energy, CT per-phase power
- **Optional controls** (off by default for new installations, enable in the integration options): operating mode select (Auto / AI / UPS), Depth of Discharge (DOD) number (30–88 %), LED panel switch. When updating from a version where these were always on, existing controls stay enabled; switch them off in the options if you do not want them.
- Polling every 30 seconds, fully local
- Tested on: **Marstek Venus E 3.0** (firmware 148; not verified via the API, the firmware number could not be read back)

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
   - **Repository**: `https://github.com/purija/marstek-venus-e`
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
   - **IP Address**: the device IP (e.g. `192.168.x.xxx`)
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

### Controls (optional)

By default the integration **only reads** from the device and never sends a command. Each control has to be enabled individually under **Settings → Devices & Services → Marstek Venus → Configure**. Disabling a control removes its entity again.

| Entity | Type | Notes |
|---|---|---|
| Operating Mode | Select | Auto / AI / UPS. Manual and Passive are not offered (they need time slots / target power); a mode set in the app shows as unknown |
| Depth of Discharge | Number | 30–88 %. Write-only: shows the last value set from HA (restored after restart, never re-sent) |
| LED Panel | Switch | Write-only: shows the last state set from HA (restored after restart, never re-sent) |

Commands share one queue with polling (at least 1 s between requests, so they never collide with a running request), are retried once on timeout, and show an error in the UI if the device rejects them or does not answer. A command issued during a poll waits only for the request that is currently running and is then sent between the remaining poll requests, so it is delayed by a few seconds at most.

---

## Energy Dashboard

The integration exposes the following sensors for use in the HA **Energy Dashboard**:

- **Solar production**: `Total Solar Energy` (disabled by default, enable it if your device has PV)
- **Grid consumption**: `Total Grid Input Energy`
- **Grid return**: `Total Grid Output Energy`
- **Battery storage**: `Battery State of Charge` + `Battery Available Capacity`

---

## Known Limitations

| Issue | Details |
|---|---|
| `Bat.GetStatus` intermittent | On firmware 148 this endpoint occasionally times out. The affected sensors keep their last value until the next successful poll, so a permanently failing endpoint shows stale values without any hint. Only if all queries of a poll fail do the entities become "unavailable". |
| Requests are serialised | The firmware drops requests that arrive while it is busy, so every request waits for the previous one plus a 1 s pause. |
| `ES.GetMode` only polled with the mode select | Nothing but the optional operating mode select reads it, so it is only queried when that control is enabled. This saves one request per poll. |
| DOD & LED state is an assumption | The device API has no GET command for these — HA shows the last value it set itself. Changes made in the Marstek app are not visible. |
| Manual / Passive mode not exposed in select | Both require parameters (time slots / target power). Not implemented as service calls yet. |
| DOD / LED need firmware ≥ 150 (per API Rev 3.1) | Rev 3.1 moves DOD, LED and Bluetooth into the `SYS` component, available on Venus C/E from firmware 150. `DOD.SET` was accepted on the test device, whose firmware number could not be read back; `Led.Ctrl` and `Ble.Adv` are untested. If the device answers "Method not found", the control shows a "not supported by this device or firmware" error. |
| `Total Solar Energy` disabled by default | The Venus E has no PV input (raw value is always 0). Rev 3.1 changed this counter to 0.01 kWh without naming a firmware, so the scaling could not be verified and no factor is applied. Enable the sensor manually if your device reports PV energy. Installations that already had the sensor keep it enabled. |
| Device firmware shown as "unknown" | `Marstek.GetDevice` often fails over unicast. If it succeeds during setup, its `ver` is shown as the device's software version. Entries created earlier have no version until re-added. |

---

## Tested Hardware

| Device | Firmware | Status |
|---|---|---|
| Marstek Venus E 3.0 | 148 (not verified via API) | ✅ Working |
| Marstek Venus C | — | Should work (same API) |
| Marstek Venus D / A | — | Partial (no EM support per API docs) |

---

## Standalone Python Script

For testing without Home Assistant, a standalone script is included:

```bash
# Requires Python 3.10+
python3 src/example.py 192.168.x.xxx
python3 src/example.py 192.168.x.xxx 49200   # custom port
```

No dependencies beyond the Python standard library.

---

## API Reference

The device uses a JSON-RPC-style protocol over UDP. Full documentation is in [`input/MarstekDeviceOpenApi-rev3-1.pdf`](input/MarstekDeviceOpenApi-rev3-1.pdf).

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

## Support

Your battery runs on sunshine, this project runs on coffee. ☕

If the integration saves you some grid power (or some nerves), a small coffee is a nice way to say thanks. It is completely voluntary and the integration stays free either way.

[![Buy me a coffee via PayPal](https://img.shields.io/badge/Buy%20me%20a%20coffee-PayPal-0070BA?style=for-the-badge&logo=paypal&logoColor=white)](https://www.paypal.com/paypalme/purija)

---

## License

MIT — see [LICENSE](LICENSE).

> **Disclaimer**: This integration is community-developed and not affiliated with or endorsed by Marstek. Use at your own risk. The Marstek Open API is provided "as is" for local use.
