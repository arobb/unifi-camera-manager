"""Direct UniFi OS REST API client for switch PoE control.

NOT used in phase 1 — PoE is controlled through the HA UniFi Network
integration's switch entities (see camera_poe.py).

Retained for phase 2 work that may require direct API access for operations
the HA integration does not expose (e.g. bulk port config, reading live stats).

Targets UniFi OS (UCG-Ultra, UDM-Pro, UDR, etc.); does NOT support the legacy
Network Application on port 8443.
"""
import base64
import json
import logging

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

log = logging.getLogger(__name__)

POE_AUTO = "auto"
POE_OFF = "off"


class UnifiLoginError(Exception):
    pass


class UnifiDeviceNotFound(Exception):
    pass


class UnifiSwitch:
    """Manages PoE state on UniFi switch ports via the UniFi OS REST API."""

    def __init__(
        self,
        host: str,
        username: str,
        password: str,
        site: str = "default",
        verify_ssl: bool = False,
    ):
        self.host = host
        self.username = username
        self.password = password
        self.site = site
        self.verify_ssl = verify_ssl
        self._session = requests.Session()
        self._session.verify = verify_ssl
        self._logged_in = False

    # ------------------------------------------------------------------
    # Auth
    # ------------------------------------------------------------------

    def _login(self) -> None:
        resp = self._session.post(
            f"https://{self.host}/api/auth/login",
            json={"username": self.username, "password": self.password},
        )
        try:
            resp.raise_for_status()
        except requests.HTTPError as exc:
            raise UnifiLoginError(f"Login failed ({resp.status_code}): {resp.text}") from exc

        csrf = resp.headers.get("X-CSRF-Token") or self._csrf_from_jwt(
            self._session.cookies.get("TOKEN", "")
        )
        if csrf:
            self._session.headers["X-CSRF-Token"] = csrf

        self._logged_in = True
        log.debug("Logged in to UniFi OS at %s", self.host)

    def _csrf_from_jwt(self, token: str) -> str | None:
        """Extract csrfToken from the TOKEN JWT cookie payload."""
        if not token:
            return None
        try:
            payload_b64 = token.split(".")[1]
            payload_b64 += "=" * (4 - len(payload_b64) % 4)
            payload = json.loads(base64.urlsafe_b64decode(payload_b64))
            return payload.get("csrfToken")
        except Exception:
            return None

    def _ensure_logged_in(self) -> None:
        if not self._logged_in:
            self._login()

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------

    def _url(self, path: str) -> str:
        return f"https://{self.host}/proxy/network/api/s/{self.site}/{path}"

    def _get(self, path: str) -> dict:
        self._ensure_logged_in()
        resp = self._session.get(self._url(path))
        if resp.status_code == 401:
            self._logged_in = False
            self._login()
            resp = self._session.get(self._url(path))
        resp.raise_for_status()
        return resp.json()

    def _put(self, path: str, payload: dict) -> dict:
        self._ensure_logged_in()
        resp = self._session.put(self._url(path), json=payload)
        if resp.status_code == 401:
            self._logged_in = False
            self._login()
            resp = self._session.put(self._url(path), json=payload)
        resp.raise_for_status()
        return resp.json()

    # ------------------------------------------------------------------
    # Device / port helpers
    # ------------------------------------------------------------------

    def get_device(self, mac: str) -> dict:
        """Return the device stat dict for the given switch MAC."""
        mac = ":".join(
            mac.lower().replace(":", "").replace("-", "")[i: i + 2]
            for i in range(0, 12, 2)
        )
        data = self._get(f"stat/device/{mac}")
        devices = data.get("data", [])
        if not devices:
            raise UnifiDeviceNotFound(f"No device found with MAC {mac}")
        return devices[0]

    def get_port_poe_mode(self, mac: str, port_idx: int) -> str | None:
        """Return the current poe_mode for the given port, or None if unset."""
        device = self.get_device(mac)
        for override in device.get("port_overrides", []):
            if override.get("port_idx") == port_idx:
                return override.get("poe_mode")
        return None

    def set_poe_mode(self, switch_mac: str, port_idx: int, mode: str) -> dict:
        """Set poe_mode on the specified port to ``'auto'`` or ``'off'``."""
        if mode not in (POE_AUTO, POE_OFF, "on"):
            raise ValueError(f"Invalid PoE mode: {mode!r}")

        device = self.get_device(switch_mac)
        device_id = device["_id"]
        overrides: list[dict] = list(device.get("port_overrides", []))

        found = False
        for override in overrides:
            if override.get("port_idx") == port_idx:
                override["poe_mode"] = mode
                found = True
                break

        if not found:
            portconf_id = next(
                (p.get("portconf_id") for p in device.get("port_table", [])
                 if p.get("port_idx") == port_idx),
                None,
            )
            if portconf_id is None:
                raise ValueError(f"Port {port_idx} not found in port_table for {switch_mac}")
            overrides.append({"port_idx": port_idx, "portconf_id": portconf_id, "poe_mode": mode})

        return self._put(f"rest/device/{device_id}", {"port_overrides": overrides})
