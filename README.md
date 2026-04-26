# UniFi Camera PoE Controller

A Home Assistant add-on that turns interior cameras on and off by cycling PoE
power on UniFi switch ports.  An [Adafruit IO](https://io.adafruit.com)
dashboard toggle provides the manual control interface.

Works alongside the HA **UniFi Network** integration — no separate UniFi
credentials are needed.

**Phase 2 (planned):** Automatic control via presence detection across UniFi
Protect, Abode, and Apple Home.  See [Phase 2](#phase-2-planned).

---

## How it works

```
Adafruit IO dashboard toggle
         │  MQTT
         ▼
  Camera PoE add-on
         │  HA REST API  (http://supervisor/core/api)
         ▼
  HA UniFi Network integration
         │  UniFi OS API
         ▼
  UniFi switch PoE ports  →  cameras on / off
```

The add-on connects to Adafruit IO over MQTT and calls HA's local REST API to
toggle the PoE switch entities that the UniFi Network integration exposes.
All configuration — credentials and port selection — is done through the
add-on's **Configuration** tab in the HA UI.

---

## Installation

### 1. Add the custom repository

In the HA add-on store, open the menu and choose **Repositories**.  Paste the
URL of this repository and click **Add**.

### 2. Install the add-on

The **Camera PoE Controller** add-on will appear in the store.  Click it,
then click **Install**.

### 3. Configure credentials and ports

Open the add-on **Configuration** tab and fill in:

| Field | Value |
|-------|-------|
| Adafruit IO username | Your io.adafruit.com login name |
| Adafruit IO key | Found at io.adafruit.com → **My Key** |
| Adafruit IO feed | Feed slug backing your dashboard toggle (e.g. `camera-poe`) |
| Camera PoE switches | One entry per camera port (entity picker, see below) |

For **Camera PoE switches**, click **Add** for each port.  An entity picker
appears — search for the port by name or type `poe` to filter to PoE switch
entities from the UniFi Network integration.  Select the entity and repeat for
each camera port.

Click **Save**.

### 4. Start the add-on

Click **Start**.  Check the **Log** tab to confirm it connects to Adafruit IO.

---

## Prerequisites

- **Home Assistant** with Supervisor support (OS or Supervised install)
- **UniFi Network integration** configured in HA and connected to your Cloud
  Gateway
- **Adafruit IO account** — free tier is sufficient.  You need a feed and a
  toggle widget on a dashboard.

---

## Using the dashboard

Use your Adafruit IO dashboard toggle as before:

- **Toggle ON (1):** cameras powered — PoE set to Auto on all configured ports
- **Toggle OFF (0):** cameras off — PoE disabled on all configured ports

The change takes effect within a few seconds.  If the toggle changes while
the add-on is offline, the correct state is applied as soon as it reconnects.

---

## Troubleshooting

**No PoE entities appear in the entity picker**
- Confirm the UniFi Network integration is connected:
  Settings → Devices & Services → UniFi Network.
- Ensure PoE is enabled on the port in the UniFi console.

**Ports configured but not responding to the toggle**
- Check the add-on **Log** tab for errors.
- Confirm the Adafruit IO feed name matches the one in your dashboard toggle.

**MQTT keeps reconnecting**
- The add-on retries automatically every 30 seconds.  Check that Adafruit IO
  credentials are correct in the Configuration tab.

---

## Phase 2 (planned)

The next phase adds automatic camera control driven by a presence pipeline:

| Signal | Integration |
|--------|-------------|
| Security system arm state | Abode |
| Phone / occupancy presence | Apple Home / HomeKit Controller |
| Wi-Fi device presence | UniFi Network device tracker |
| Entry-point motion | UniFi Protect |

The design requires multiple signals to agree before toggling, to avoid false
triggers.  The Adafruit IO toggle remains as a manual override.

---

## Repository layout

```
.
├── README.md
├── AGENT.md                    ← engineering docs for AI agents
├── repository.yaml             ← HA custom add-on repository manifest
└── camera-poe/                 ← the add-on (installed by HA from this dir)
    ├── config.yaml             ← add-on manifest, options schema
    ├── Dockerfile
    ├── DOCS.md                 ← shown in the HA add-on info tab
    └── app/
        ├── requirements.txt
        ├── main.py             ← entrypoint
        ├── camera_poe.py       ← MQTT service + HA API calls
        └── unifi_switch.py     ← direct UniFi OS API client (phase 2)
```
