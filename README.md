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
Port selection is done through an **ingress web page** in the HA sidebar —
no YAML editing or file copying required.

---

## Installation

### 1. Add the custom repository

In Home Assistant:

**Settings → Add-ons → Add-on store → ⋮ (top-right) → Repositories**

Paste the URL of this repository and click **Add**.

### 2. Install the add-on

The **Camera PoE Controller** add-on will appear in the store.  Click it,
then click **Install**.

### 3. Set Adafruit IO credentials

Open the add-on **Configuration** tab and fill in:

| Field | Value |
|-------|-------|
| Adafruit IO username | Your io.adafruit.com login name |
| Adafruit IO key | Found at io.adafruit.com → **My Key** |
| Adafruit IO feed | The feed slug backing your dashboard toggle (e.g. `camera-poe`) |

Click **Save**.

### 4. Start the add-on

Click **Start**.  The add-on appears as **Camera PoE** in the HA sidebar once
running.

### 5. Select camera ports

Open **Camera PoE** in the sidebar.  The page lists every PoE-capable switch
port from the UniFi Network integration, **grouped by switch**.  Check the
ports that power your interior cameras and click **Save selection**.

The add-on reads the selection immediately — no restart needed.

---

## Prerequisites

- **Home Assistant** (OS, Supervised, or any install with the Supervisor)
- **UniFi Network integration** configured in HA and connected to your Cloud
  Gateway
- **Adafruit IO account** — free tier is sufficient.  You need a feed and a
  toggle widget on a dashboard.

---

## Using the dashboard

Use your Adafruit IO dashboard toggle as before:

- **Toggle ON (1):** cameras powered — PoE set to Auto on all selected ports
- **Toggle OFF (0):** cameras off — PoE disabled on all selected ports

The change takes effect within a few seconds.  If the toggle is changed while
the add-on is offline, the correct state is applied as soon as it reconnects.

---

## Sidebar panel

The **Camera PoE** panel in the HA sidebar serves two purposes:

1. **Port selection** — shows all UniFi PoE ports grouped by switch, with
   checkboxes.  Check the ports to control and click **Save selection**.

2. **Status** — shows whether cameras are currently on or off, the last action
   timestamp, and whether the Adafruit IO MQTT connection is active.

No page refresh is needed after saving — the MQTT service picks up the new
selection on the next feed update or add-on restart.

---

## Troubleshooting

**No ports appear in the Camera PoE panel**
- Wait ~60 seconds after HA starts for the UniFi integration to finish loading,
  then refresh the page.
- Confirm the UniFi Network integration is connected:
  Settings → Devices & Services → UniFi Network.
- Confirm PoE is enabled on the port in the UniFi console.

**Ports listed but don't respond to the toggle**
- Check the add-on **Log** tab for errors.
- Confirm the Adafruit IO feed name matches the one in your dashboard toggle.

**"MQTT disconnected" shown in the panel**
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
        ├── web.py              ← ingress web server (port selection UI)
        └── unifi_switch.py     ← direct UniFi OS API client (phase 2)
```
