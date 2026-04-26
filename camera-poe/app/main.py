#!/usr/bin/env python3
"""Add-on entrypoint.

Reads /data/options.json (written by the HA Supervisor from the add-on options
form), then starts two long-running components:
  - CameraPoeMQTT  — Adafruit IO MQTT listener, runs in a background thread
  - web.run()      — Flask ingress web server, runs in the main thread
"""
import json
import logging
import sys
import threading
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
        log.error(
            "%s not found — configure Adafruit IO credentials in the add-on options",
            OPTIONS_FILE,
        )
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
            "in the add-on options."
        )
        sys.exit(1)

    log.info("Starting Camera PoE Controller")
    log.info("  Adafruit IO user : %s", username)
    log.info("  Adafruit IO feed : %s", feed)

    from camera_poe import CameraPoeMQTT
    import web

    mqtt = CameraPoeMQTT(aio_username=username, aio_key=key, aio_feed=feed)

    mqtt_thread = threading.Thread(target=mqtt.run, name="camera-poe-mqtt", daemon=True)
    mqtt_thread.start()

    # Web server blocks in the main thread; if it exits the add-on exits too.
    web.run(port=8099)


if __name__ == "__main__":
    main()
