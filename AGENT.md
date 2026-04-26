# Camera PoE Controller — Agent Harness Documentation

## Project purpose

Automates the power state of interior CCTV cameras by controlling PoE on the
UniFi switches that feed them.  Cameras are powered off when occupants are home
(privacy) and powered on when away (security).

**Current phase (Phase 1):** Adafruit IO dashboard toggle → UniFi PoE.
**Planned phase (Phase 2):** Automatic control driven by a presence pipeline
spanning UniFi Protect, Abode, Apple Home, and UniFi Network device tracking.

---

## Runtime environment

The project is packaged as a **Home Assistant add-on**.  The target hardware
is a **Home Assistant Green** (HAOS on aarch64).  The add-on is a Docker
container installed via a custom HA add-on repository — no SSH, no file copying.

- The Supervisor writes add-on options to `/data/options.json`.  All
  configuration (credentials and switch entity IDs) comes from this file.
- The HA REST API is available at `http://supervisor/core/api` authenticated
  with the `SUPERVISOR_TOKEN` environment variable (injected by the Supervisor
  when `homeassistant_api: true` is set in `config.yaml`).

---

## Repository layout

```
.
├── AGENT.md                              ← this file
├── README.md                             ← user-facing install / usage guide
├── repository.yaml                       ← HA add-on repository manifest
├── camera-poe/                           ← the HA add-on
│   ├── config.yaml                       ← add-on manifest + options schema
│   ├── Dockerfile                        ← FROM python:3.11-alpine (multi-arch via Docker Hub)
│   ├── DOCS.md                           ← shown in HA add-on info tab
│   └── app/
│       ├── requirements.txt
│       ├── main.py                       ← entrypoint: reads options, runs MQTT
│       ├── camera_poe.py                 ← MQTT listener + HA API calls
│       └── unifi_switch.py              ← direct UniFi OS API (phase 2 only)
└── adafruit-unifi/                       ← original daemon (gitignored, reference only)
```

---

## Key files

### `camera-poe/config.yaml`

Add-on manifest.  Key fields:
- `homeassistant_api: true` — grants access to HA REST API via `SUPERVISOR_TOKEN`
- `schema` — defines the options form in the HA add-on Configuration tab.

Current options:

| Key | Schema type | Description |
|-----|-------------|-------------|
| `adafruit_io_username` | `str` | Adafruit IO account username |
| `adafruit_io_key` | `password` | Adafruit IO API key (masked in UI) |
| `adafruit_io_feed` | `str` | Feed slug |
| `camera_poe_switches` | `- str` | List of HA switch entity IDs; renders a text input per entry in the Configuration tab. Note: `selector:` syntax is valid in HA automations but **not** in add-on `config.yaml` schemas — using it causes the add-on to fail Supervisor validation and disappear from the store. |

### `camera-poe/app/main.py`

Entry point.  Reads `/data/options.json`, validates credentials, passes all
options to `CameraPoeMQTT`, and calls `mqtt.run()` which blocks in the main
thread.

### `camera-poe/app/camera_poe.py`

**Class:** `CameraPoeMQTT(aio_username, aio_key, aio_feed, switches)`

`switches` is passed at construction from `options.json`; changing it requires
an add-on restart (standard HA add-on behaviour).

Key methods:
- `set_cameras_on(bool)` — sole actuator for camera power.  Checks current HA
  entity state before calling `switch/turn_on` or `switch/turn_off` to skip
  no-op API calls.
- `run()` — blocking MQTT loop with 30 s reconnect backoff.

### `camera-poe/app/unifi_switch.py`

**Not used in phase 1.**  Direct HTTP client for the UniFi OS REST API.  Kept
for phase 2 work that requires operations the HA integration does not expose.

Key API paths (relative to `https://{host}/`):
- `POST /api/auth/login` — login; extracts CSRF token from TOKEN JWT cookie
- `GET /proxy/network/api/s/{site}/stat/device/{mac}` — device stats
- `PUT /proxy/network/api/s/{site}/rest/device/{id}` — update port_overrides

---

## Configuration reference

### Add-on options (`/data/options.json`)

| Key | Type | Description |
|-----|------|-------------|
| `adafruit_io_username` | str | Adafruit IO account username |
| `adafruit_io_key` | str | Adafruit IO API key |
| `adafruit_io_feed` | str | Feed slug, e.g. `camera-poe` |

Credentials are entered via the HA add-on Configuration tab.

### Switch selection (`camera_poe_switches` in `/data/options.json`)

Plain JSON array of HA switch entity IDs, set in the add-on Configuration tab:
```json
["switch.front_camera_poe", "switch.driveway_camera_poe"]
```

Changing this requires an add-on restart (standard HA add-on behaviour).

---

## README maintenance

`README.md` is the user-facing install and usage guide.  **Keep it in sync
with code changes.**  Update it when:

- The installation steps change
- An add-on option is added, renamed, or removed
- The ingress UI gains or loses a feature
- A phase 2 feature ships and changes the normal operation story
- The troubleshooting section becomes stale

Do not add implementation detail or API references to `README.md` — those
belong here.  `README.md` describes what the user does; `AGENT.md` describes
how the code works.

---

## Phase 2 — Presence detection (planned)

The goal is to drive `CameraPoeMQTT.set_cameras_on` automatically.

Planned signal sources:

| Source | Signal | HA integration |
|--------|--------|----------------|
| **Abode** | Security system arm/disarm | Abode integration |
| **Apple Home** | Occupancy sensors / phone presence | HomeKit Controller |
| **UniFi Network** | Device-on-network (phone association) | UniFi integration |
| **UniFi Protect** | Entry-point motion / person detection | UniFi Protect integration |

Design principle: require multiple independent signals to agree before toggling,
to avoid false triggers (one phone leaving ≠ everyone left).

The Adafruit IO feed stays active as a manual override.

Implementation options (to be decided):
- A second add-on that calls `set_cameras_on` via the HA REST API
- Additional logic in `camera_poe.py` subscribing to HA state changes via
  the Supervisor WebSocket
- An AppDaemon app (for users not on HA OS) using the existing `set_cameras_on`
  method pattern

---

## Development notes

- Python 3.11 inside the add-on (`FROM python:3.11-alpine` in Dockerfile).
  Cannot use 3.12+ until `adafruit-io` drops its `ez_setup.py` / `distutils` dependency.
- No database; source of truth for desired camera state is the Adafruit IO feed.
  On restart the app re-reads the feed and re-applies the state.
- `/data/` is persisted across add-on restarts by the Supervisor.
- The MQTT thread is a daemon thread — it stops when the main thread (Flask)
  exits.  `stop()` on `CameraPoeMQTT` signals it to exit its sleep/retry loop
  cleanly.
- The Flask development server (`use_reloader=False`) is appropriate here; the
  add-on is single-instance and low-traffic.

---

## External API references

### Adafruit IO

- Dashboard / feed management: https://io.adafruit.com
- Python library: https://adafruit-io-python-client.readthedocs.io/
- MQTT broker: `io.adafruit.com:1883`
- Feed topic: `{username}/feeds/{feed_name}`

### HA Supervisor REST API (used by this add-on)

Base URL: `http://supervisor/core/api`  
Auth header: `Authorization: Bearer $SUPERVISOR_TOKEN`

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/template` | Render a Jinja2 template (entity/device discovery) |
| GET | `/states/{entity_id}` | Get current entity state |
| POST | `/services/switch/turn_on` | Turn on switch entity |
| POST | `/services/switch/turn_off` | Turn off switch entity |

### UniFi OS network API (phase 2)

See `unifi_switch.py` for full details.  All paths via
`https://{host}/proxy/network/api/s/{site}/`.
