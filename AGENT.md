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

- The Supervisor writes add-on options to `/data/options.json`.
- Persistent state (selected switch entities, last camera state) is written to
  `/data/` by the add-on itself.
- The HA REST API is available at `http://supervisor/core/api` authenticated
  with the `SUPERVISOR_TOKEN` environment variable (injected by the Supervisor
  when `homeassistant_api: true` is set in `config.yaml`).
- The add-on exposes a web UI via HA ingress on port 8099.

---

## Repository layout

```
.
├── AGENT.md                              ← this file
├── README.md                             ← user-facing install / usage guide
├── repository.yaml                       ← HA add-on repository manifest
├── camera-poe/                           ← the HA add-on
│   ├── config.yaml                       ← add-on manifest + options schema
│   ├── Dockerfile                        ← FROM python:3.12-alpine (multi-arch via Docker Hub)
│   ├── DOCS.md                           ← shown in HA add-on info tab
│   └── app/
│       ├── requirements.txt
│       ├── main.py                       ← entrypoint: reads options, starts threads
│       ├── camera_poe.py                 ← MQTT listener + HA API calls
│       ├── web.py                        ← Flask ingress UI
│       └── unifi_switch.py              ← direct UniFi OS API (phase 2 only)
└── adafruit-unifi/                       ← original daemon (gitignored, reference only)
```

---

## Key files

### `camera-poe/config.yaml`

Add-on manifest.  Key fields:
- `homeassistant_api: true` — grants access to HA REST API via `SUPERVISOR_TOKEN`
- `ingress: true` / `ingress_port: 8099` — embeds the web UI in the HA sidebar
- `schema` — defines the options form rendered in the HA add-on Configuration tab.
  Current options: `adafruit_io_username` (str), `adafruit_io_key` (password),
  `adafruit_io_feed` (str).

### `camera-poe/app/main.py`

Entry point.  Reads `/data/options.json`, validates credentials, starts the
MQTT service in a daemon thread, then runs the Flask web server in the main
thread.  If the web server exits the container exits (Supervisor restarts it).

### `camera-poe/app/camera_poe.py`

**Class:** `CameraPoeMQTT`

Reads switch selection from `/data/switches.json` at call time (not cached),
so the web UI's saved selection takes effect without a restart.

Key methods:
- `set_cameras_on(bool)` — the sole actuator for camera power.  Reads current
  HA entity state before calling `switch/turn_on` or `switch/turn_off` to avoid
  no-op API calls.  Writes result to `/data/state.json`.
- `run()` — blocking MQTT loop with 30 s reconnect backoff.

State file `/data/state.json` shape:
```json
{ "cameras": "on|off", "mqtt_connected": true, "last_action": "ISO8601", "error": null }
```

### `camera-poe/app/web.py`

Flask application served on port 8099 (ingress).  Two routes:
- `GET /` — renders the port selection page.  Calls `POST /api/template` on
  the HA API using the same Jinja2 discovery template as
  `tools/discover_poe_entities.py`.  Reads `/data/switches.json` to pre-check
  the current selection.  Reads `/data/state.json` for the status banner.
- `POST /save` — writes the checked entity IDs to `/data/switches.json`,
  redirects to `/?saved=1`.

The ingress proxy strips the HA path prefix before forwarding to Flask, so all
routes are at `/` relative to the add-on.  Do not use `url_for()` with
absolute URLs or `SERVER_NAME`.

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

### Switch selection (`/data/switches.json`)

Plain JSON array of HA switch entity IDs, written by the ingress web UI:
```json
["switch.front_camera_poe", "switch.driveway_camera_poe"]
```

Set by the user via the Camera PoE panel in the HA sidebar.  The MQTT service
reads this file on every `set_cameras_on` call, so changes take effect without
a restart.

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

- Python 3.12 inside the add-on (set in `build.yaml` base images).
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
