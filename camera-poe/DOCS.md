# Camera PoE Controller

Controls interior camera power by cycling PoE on UniFi switch ports.
An Adafruit IO dashboard toggle provides the manual on/off interface.

## Setup

Open the add-on **Configuration** tab and fill in all fields, then click
**Save** and **Start** the add-on.

### Adafruit IO credentials

| Field | Value |
|-------|-------|
| Adafruit IO username | Your io.adafruit.com login name |
| Adafruit IO key | Found at io.adafruit.com → **My Key** |
| Adafruit IO feed | The slug of the feed backing your dashboard toggle (e.g. `camera-poe`) |

### Camera PoE switches

Click **Add** for each camera port and type its HA entity ID.

**To find the entity IDs:** start the add-on with this field empty and open
the **Log** tab.  On every startup the add-on queries HA and prints all
available UniFi PoE switch entities grouped by switch:

```
INFO  --- Available UniFi PoE switch entities ---
INFO    Living Room Switch
INFO      switch.front_camera_poe       (Front Camera PoE)
INFO      switch.hallway_camera_poe     (Hallway Camera PoE)
INFO    Garage Switch
INFO      switch.driveway_camera_poe    (Driveway Camera PoE)
INFO    Copy the entity IDs above into 'Camera PoE switches' in the Configuration tab.
INFO  -------------------------------------------
```

Copy the entity IDs you want to control into the Configuration tab, save,
and restart the add-on.  The list refreshes on every restart so you can
re-check it any time.

## Requirements

- **UniFi Network integration** must be configured in Home Assistant and
  connected to your Cloud Gateway.  The add-on controls cameras through
  the integration's existing switch entities; no separate UniFi credentials
  are required here.
- **Adafruit IO** account with a feed and a toggle widget on a dashboard.

## Troubleshooting

**No PoE entities appear in the entity picker**
- Confirm the UniFi Network integration is connected:
  Settings → Devices & Services → UniFi Network.
- Ensure PoE is enabled on the port in the UniFi console.
- If the integration just loaded, wait ~60 seconds and try again.

**Ports configured but not responding to the toggle**
- Check the add-on **Log** tab for errors.
- Confirm the Adafruit IO feed name matches the toggle widget on your dashboard.

**MQTT keeps reconnecting**
- Check that the Adafruit IO credentials are correct in the Configuration tab.
