"""Ingress web UI for port selection and status display.

Accessible from the HA sidebar under "Camera PoE".  Queries the running HA
instance to discover UniFi PoE switch entities grouped by physical switch,
lets the user check which ports to control, and saves the selection to
/data/switches.json for the MQTT service to read.
"""
import json
import logging
import os
from collections import defaultdict
from pathlib import Path

import requests as http_req
from flask import Flask, redirect, render_template_string, request, url_for

log = logging.getLogger(__name__)

SWITCHES_FILE = Path("/data/switches.json")
STATE_FILE = Path("/data/state.json")
HA_API = "http://supervisor/core/api"
_SUPERVISOR_TOKEN = os.environ.get("SUPERVISOR_TOKEN", "")

# Jinja2 template evaluated by HA's template engine.
# Produces a JSON list of {entity_id, device_name, friendly_name, state} objects
# for all UniFi PoE switch entities, grouped by their parent device (switch).
_DISCOVERY_TEMPLATE = """\
{%- set ns = namespace(entities=[]) -%}
{%- for entity_id in integration_entities('unifi')
    | select('match', 'switch\\..*_poe')
    | list -%}
  {%- set ns.entities = ns.entities + [{
    'entity_id':     entity_id,
    'device_name':   device_attr(entity_id, 'name') | default('Unknown Switch'),
    'friendly_name': state_attr(entity_id, 'friendly_name') | default(entity_id),
    'state':         states(entity_id)
  }] -%}
{%- endfor -%}
{{ ns.entities | tojson }}\
"""

_PAGE = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Camera PoE Controller</title>
  <style>
    :root { --primary: #03a9f4; --on-primary: #fff;
            --surface: #fafafa; --border: #e0e0e0;
            --text: #212121; --muted: #757575; --green: #4caf50; --red: #f44336; }
    @media (prefers-color-scheme: dark) {
      :root { --surface: #1e1e1e; --border: #333; --text: #e0e0e0; --muted: #9e9e9e; }
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
           font-size: 14px; color: var(--text); padding: 16px; max-width: 640px; }
    h1 { font-size: 1.25rem; font-weight: 500; margin-bottom: 16px; }
    .card { background: var(--surface); border: 1px solid var(--border);
            border-radius: 8px; padding: 12px 16px; margin-bottom: 16px; }
    .status-row { display: flex; align-items: center; gap: 8px; }
    .badge { display: inline-block; padding: 2px 8px; border-radius: 12px;
             font-size: 0.8rem; font-weight: 600; text-transform: uppercase; }
    .badge-on  { background: #e8f5e9; color: var(--green); }
    .badge-off { background: #fce4ec; color: var(--red); }
    .badge-unknown { background: var(--border); color: var(--muted); }
    .meta { color: var(--muted); font-size: 0.8rem; margin-top: 4px; }
    .error-msg { color: var(--red); font-size: 0.85rem; margin-top: 6px; }
    h2 { font-size: 0.7rem; font-weight: 600; text-transform: uppercase;
         letter-spacing: 0.08em; color: var(--muted); margin: 16px 0 8px; }
    .port { display: flex; align-items: center; padding: 8px 0;
            border-bottom: 1px solid var(--border); }
    .port:last-child { border-bottom: none; }
    .port input[type=checkbox] { width: 18px; height: 18px; margin-right: 12px;
                                  accent-color: var(--primary); cursor: pointer; flex-shrink: 0; }
    .port label { cursor: pointer; flex: 1; }
    .port .eid { display: block; font-family: monospace; font-size: 0.75rem;
                 color: var(--muted); margin-top: 2px; }
    .port .pstate { font-size: 0.75rem; color: var(--muted); margin-left: 8px; }
    .actions { margin-top: 20px; display: flex; align-items: center; gap: 12px; }
    button { background: var(--primary); color: var(--on-primary); border: none;
             padding: 10px 20px; border-radius: 6px; cursor: pointer;
             font-size: 0.9rem; font-weight: 500; }
    button:hover { filter: brightness(1.1); }
    .saved { color: var(--green); font-size: 0.85rem; }
    .notice { padding: 12px; border-radius: 6px; font-size: 0.85rem;
              background: #fff3e0; color: #e65100; }
  </style>
</head>
<body>
  <h1>Camera PoE Controller</h1>

  <div class="card">
    <div class="status-row">
      <span>Cameras:</span>
      {% if state %}
        <span class="badge badge-{{ state.cameras }}">{{ state.cameras }}</span>
        {% if not state.mqtt_connected %}
          <span style="color: var(--red); font-size:0.8rem">⚠ MQTT disconnected</span>
        {% endif %}
      {% else %}
        <span class="badge badge-unknown">unknown</span>
      {% endif %}
    </div>
    {% if state and state.last_action %}
      <div class="meta">Last action: {{ state.last_action }}</div>
    {% endif %}
    {% if state and state.error %}
      <div class="error-msg">{{ state.error }}</div>
    {% endif %}
  </div>

  {% if discover_error %}
    <div class="notice">
      Could not load UniFi entities: {{ discover_error }}<br>
      Ensure the UniFi Network integration is connected, then
      <a href="/">refresh</a>.
    </div>
  {% elif not devices %}
    <div class="notice">
      No UniFi PoE switch entities found.<br>
      Check that the UniFi Network integration is active and that PoE-capable
      ports exist in your site.  <a href="/">Refresh</a> after the integration loads.
    </div>
  {% else %}
    <form method="post" action="/save">
      {% for device_name, ports in devices | dictsort %}
        <h2>{{ device_name }}</h2>
        <div class="card" style="padding: 0 16px;">
          {% for p in ports | sort(attribute='entity_id') %}
            <div class="port">
              <input type="checkbox" name="entity"
                     id="{{ p.entity_id }}" value="{{ p.entity_id }}"
                     {% if p.entity_id in selected %}checked{% endif %}>
              <label for="{{ p.entity_id }}">
                {{ p.friendly_name }}
                <span class="eid">{{ p.entity_id }}</span>
              </label>
              <span class="pstate">{{ p.state }}</span>
            </div>
          {% endfor %}
        </div>
      {% endfor %}

      <div class="actions">
        <button type="submit">Save selection</button>
        {% if saved %}<span class="saved">✓ Saved</span>{% endif %}
      </div>
    </form>
  {% endif %}
</body>
</html>
"""


def _ha_headers() -> dict:
    return {
        "Authorization": f"Bearer {_SUPERVISOR_TOKEN}",
        "Content-Type": "application/json",
    }


def _discover_entities() -> tuple[dict[str, list], str | None]:
    """Return (devices_by_name, error_string_or_None)."""
    try:
        resp = http_req.post(
            f"{HA_API}/template",
            headers=_ha_headers(),
            json={"template": _DISCOVERY_TEMPLATE},
            timeout=15,
        )
        resp.raise_for_status()
        entities = json.loads(resp.text)
    except Exception as exc:
        log.error("Entity discovery failed: %s", exc)
        return {}, str(exc)

    by_device: dict[str, list] = defaultdict(list)
    for e in entities:
        by_device[e["device_name"]].append(e)
    return dict(by_device), None


def _load_selected() -> list[str]:
    if SWITCHES_FILE.exists():
        try:
            return json.loads(SWITCHES_FILE.read_text())
        except Exception:
            pass
    return []


def _load_state() -> dict | None:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            pass
    return None


def create_app() -> Flask:
    app = Flask(__name__)

    @app.route("/")
    def index():
        devices, discover_error = _discover_entities()
        return render_template_string(
            _PAGE,
            devices=devices,
            selected=_load_selected(),
            state=_load_state(),
            discover_error=discover_error,
            saved=request.args.get("saved") == "1",
        )

    @app.route("/save", methods=["POST"])
    def save():
        chosen = request.form.getlist("entity")
        SWITCHES_FILE.write_text(json.dumps(chosen))
        log.info("Saved switch selection: %s", chosen)
        return redirect("/?saved=1")

    return app


def run(port: int = 8099) -> None:
    app = create_app()
    app.run(host="0.0.0.0", port=port, use_reloader=False)
