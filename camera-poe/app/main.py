#!/usr/bin/env python3
"""Add-on entrypoint.

Reads /data/options.json (written by the Supervisor from the add-on
Configuration tab) and runs the Adafruit IO MQTT listener.
"""
import json
import logging
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger(__name__)

OPTIONS_FILE = Path("/data/options.json")


def load_options() -> dict:
    try:
        return json.loads(OPTIONS_FILE.read_text())
    except FileNotFoundError:
        log.error("%s not found — configure the add-on options and restart", OPTIONS_FILE)
        sys.exit(1)
    except json.JSONDecodeError as exc:
        log.error("Failed to parse %s: %s", OPTIONS_FILE, exc)
        sys.exit(1)


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
    log.info("  Switch entities   : %s", switches if switches else "(none configured)")

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
