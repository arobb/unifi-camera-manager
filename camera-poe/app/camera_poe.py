"""Adafruit IO MQTT listener → UniFi switch PoE control via HA REST API.

Configuration is read at runtime from two files written by the Supervisor:
  /data/options.json   — Adafruit IO credentials + feed name (from add-on options form)
  /data/switches.json  — list of HA entity IDs to control (saved by the ingress web UI)

State is written to /data/state.json so the ingress web UI can display it.
"""
import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path

import requests
from Adafruit_IO import Client as AIO_Client
from Adafruit_IO import MQTTClient as AIO_MQTTClient
from Adafruit_IO.errors import RequestError

log = logging.getLogger(__name__)

SWITCHES_FILE = Path("/data/switches.json")
STATE_FILE = Path("/data/state.json")
HA_API = "http://supervisor/core/api"
_SUPERVISOR_TOKEN = os.environ.get("SUPERVISOR_TOKEN", "")
_RECONNECT_DELAY_S = 30


def _ha_headers() -> dict:
    return {
        "Authorization": f"Bearer {_SUPERVISOR_TOKEN}",
        "Content-Type": "application/json",
    }


class CameraPoeMQTT:
    """Watches an Adafruit IO feed and applies PoE state to HA switch entities."""

    def __init__(self, aio_username: str, aio_key: str, aio_feed: str):
        self._username = aio_username
        self._key = aio_key
        self._feed = aio_feed
        self._stop = False

    # ------------------------------------------------------------------
    # Public API (also called by phase-2 automations)
    # ------------------------------------------------------------------

    def set_cameras_on(self, cameras_on: bool) -> None:
        """Turn all configured camera PoE switch entities on or off."""
        switches = self._load_switches()
        if not switches:
            log.warning("No switch ports configured — open the Camera PoE panel to select ports")
            self._write_state(cameras_on, mqtt_connected=True, error="No ports configured")
            return

        service = "turn_on" if cameras_on else "turn_off"
        target = "on" if cameras_on else "off"
        log.info("Setting camera PoE → %s (%d port(s))", target, len(switches))

        errors = []
        for entity_id in switches:
            try:
                resp = requests.get(
                    f"{HA_API}/states/{entity_id}",
                    headers=_ha_headers(),
                    timeout=10,
                )
                resp.raise_for_status()
                if resp.json().get("state") == target:
                    log.debug("  %s already %s, skipping", entity_id, target)
                    continue

                requests.post(
                    f"{HA_API}/services/switch/{service}",
                    headers=_ha_headers(),
                    json={"entity_id": entity_id},
                    timeout=10,
                ).raise_for_status()
                log.info("  %s → %s", entity_id, target)

            except Exception as exc:
                log.error("  Error setting %s: %s", entity_id, exc)
                errors.append(str(exc))

        self._write_state(cameras_on, mqtt_connected=True, error=errors[0] if errors else None)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_switches(self) -> list[str]:
        if SWITCHES_FILE.exists():
            try:
                return json.loads(SWITCHES_FILE.read_text())
            except Exception:
                pass
        return []

    def _write_state(self, cameras_on: bool, *, mqtt_connected: bool, error: str | None = None):
        STATE_FILE.write_text(json.dumps({
            "cameras": "on" if cameras_on else "off",
            "mqtt_connected": mqtt_connected,
            "last_action": datetime.now().isoformat(timespec="seconds"),
            "error": error,
        }))

    # ------------------------------------------------------------------
    # MQTT callbacks
    # ------------------------------------------------------------------

    def _on_connect(self, client: AIO_MQTTClient) -> None:
        log.info("Connected to Adafruit IO MQTT")
        client.subscribe(self._feed)

        try:
            latest = AIO_Client(self._username, self._key).receive(self._feed)
            log.info("Current feed value: %r — applying", latest.value)
            self._handle_value(latest.value)
        except RequestError as exc:
            if "404" in str(exc):
                log.warning("Feed %r has no data yet, skipping initial sync", self._feed)
            else:
                log.error("Error reading initial feed state: %s", exc)
        except Exception as exc:
            log.error("Error during initial sync: %s", exc)

    def _on_message(self, client: AIO_MQTTClient, feed_id: str, payload: str) -> None:
        if feed_id != self._feed:
            return
        log.info("Feed update → %r", payload)
        self._handle_value(payload)

    def _handle_value(self, value: str) -> None:
        try:
            self.set_cameras_on(int(value) > 0)
        except (ValueError, TypeError):
            log.warning("Unrecognised feed value %r, ignoring", value)

    # ------------------------------------------------------------------
    # Blocking run loop
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Connect to Adafruit IO and block until stopped.  Reconnects on error."""
        while not self._stop:
            try:
                client = AIO_MQTTClient(self._username, self._key)
                client.on_connect = self._on_connect
                client.on_message = self._on_message
                client.connect()
                client.loop_blocking()
            except Exception as exc:
                if self._stop:
                    break
                log.warning("MQTT error: %s — retrying in %ds", exc, _RECONNECT_DELAY_S)
                self._write_state(False, mqtt_connected=False, error=str(exc))
                time.sleep(_RECONNECT_DELAY_S)

        log.info("MQTT listener stopped")

    def stop(self) -> None:
        self._stop = True
