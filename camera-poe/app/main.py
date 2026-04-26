#!/usr/bin/env python3
"""Add-on entrypoint.

Reads /data/options.json (written by the Supervisor from the add-on
Configuration tab) and runs the Adafruit IO MQTT listener.
"""
import json
import logging
import os
import sys
from collections import defaultdict
from pathlib import Path

import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger(__name__)

OPTIONS_FILE = Path("/data/options.json")
HA_API = "http://supervisor/core/api"
_SUPERVISOR_TOKEN = os.environ.get("SUPERVISOR_TOKEN", "")

# Jinja2 template evaluated by the HA template engine.  Returns a JSON list of
# {entity_id, device_name, friendly_name} for all UniFi PoE switch entities.
_DISCOVERY_TEMPLATE = """\
{%- set ns = namespace(entities=[]) -%}
{%- for entity_id in integration_entities('unifi')
    | select('match', 'switch\\..*_poe') | list -%}
  {%- set ns.entities = ns.entities + [{
    'entity_id':     entity_id,
    'device_name':   device_attr(entity_id, 'name') | default('Unknown Switch'),
    'friendly_name': state_attr(entity_id, 'friendly_name') | default(entity_id)
  }] -%}
{%- endfor -%}
{{ ns.entities | tojson }}\
"""


def load_options() -> dict:
    try:
        return json.loads(OPTIONS_FILE.read_text())
    except FileNotFoundError:
        log.error("%s not found — configure the add-on options and restart", OPTIONS_FILE)
        sys.exit(1)
    except json.JSONDecodeError as exc:
        log.error("Failed to parse %s: %s", OPTIONS_FILE, exc)
        sys.exit(1)


def log_available_switches() -> None:
    """Query HA for UniFi PoE entities and log them grouped by switch.

    Called on every startup so the user can copy entity IDs from the Log tab
    into the Configuration tab without needing any external tools.
    """
    try:
        resp = requests.post(
            f"{HA_API}/template",
            headers={
                "Authorization": f"Bearer {_SUPERVISOR_TOKEN}",
                "Content-Type": "application/json",
            },
            json={"template": _DISCOVERY_TEMPLATE},
            timeout=15,
        )
        resp.raise_for_status()
        entities = json.loads(resp.text)
    except Exception as exc:
        log.warning("Could not discover UniFi PoE entities: %s", exc)
        log.warning("Ensure the UniFi Network integration is loaded, then restart the add-on.")
        return

    if not entities:
        log.warning("No UniFi PoE switch entities found.")
        log.warning("Check that the UniFi Network integration is connected and PoE ports are enabled.")
        return

    by_device = defaultdict(list)
    for e in entities:
        by_device[e["device_name"]].append(e)

    log.info("--- Available UniFi PoE switch entities ---")
    for device_name in sorted(by_device):
        log.info("  %s", device_name)
        for e in sorted(by_device[device_name], key=lambda x: x["entity_id"]):
            log.info("    %s  (%s)", e["entity_id"], e["friendly_name"])
    log.info("  Copy the entity IDs above into 'Camera PoE switches' in the Configuration tab.")
    log.info("-------------------------------------------")


def main() -> None:
    opts = load_options()

    username = opts.get("adafruit_io_username", "")
    key = opts.get("adafruit_io_key", "")
    feed = opts.get("adafruit_io_feed", "")

    if not all([username, key, feed]):
        log.error(
            "Adafruit IO credentials are incomplete. "
            "Set adafruit_io_username, adafruit_io_key, and adafruit_io_feed "
            "in the add-on Configuration tab."
        )
        sys.exit(1)

    switches = opts.get("camera_poe_switches", [])

    log.info("Starting Camera PoE Controller")
    log.info("  Adafruit IO feed  : %s", feed)
    log.info("  Configured ports  : %s", switches if switches else "(none — see entity list below)")

    log_available_switches()

    from camera_poe import CameraPoeMQTT

    mqtt = CameraPoeMQTT(
        aio_username=username,
        aio_key=key,
        aio_feed=feed,
        switches=switches,
    )
    mqtt.run()


if __name__ == "__main__":
    main()
