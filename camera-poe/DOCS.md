# Camera PoE Controller

Controls interior camera power by cycling PoE on UniFi switch ports.
An Adafruit IO dashboard toggle provides the manual on/off interface.

## Setup

### 1. Configure Adafruit IO credentials

In the add-on **Configuration** tab, fill in:
- **Adafruit IO username** — your io.adafruit.com login name
- **Adafruit IO key** — found at io.adafruit.com → My Key
- **Adafruit IO feed** — the slug of the feed backing your dashboard toggle
  (e.g. `camera-poe`)

Click **Save**, then **Start** the add-on.

### 2. Select camera ports

Open the **Camera PoE** panel in the HA sidebar.  The page lists every
PoE-capable switch port from the UniFi Network integration, grouped by switch.
Check the ports that power your interior cameras and click **Save selection**.

The add-on reads this selection immediately — no restart needed.

## Requirements

- **UniFi Network integration** must be configured in Home Assistant and
  connected to your Cloud Gateway.  The add-on controls cameras through
  the integration's existing switch entities; no separate UniFi credentials
  are required here.
- **Adafruit IO** account with a feed and a toggle widget on a dashboard.

## Troubleshooting

**No ports appear in the Camera PoE panel**
- Wait ~60 seconds after HA starts for the UniFi integration to finish loading,
  then refresh the page.
- Confirm the UniFi Network integration shows as connected:
  Settings → Devices & Services → UniFi Network.
- Ensure PoE is enabled on the port in the UniFi console.

**Ports appear but don't respond to the toggle**
- Check the add-on log (Log tab) for errors.
- Confirm the Adafruit IO feed name matches the one in your dashboard toggle.

**MQTT disconnected warning in status**
- The add-on retries the Adafruit IO connection every 30 seconds automatically.
  Check that the Adafruit IO credentials are correct.
