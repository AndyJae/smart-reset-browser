"""
camera_plugins/birddog/transport.py — BirdDog REST/JSON transport.

Implements CameraProtocol for the BirdDog REST API:
  - HTTP GET/POST on port 8080
  - Command encoding: "GET /path" or "POST /path {json_body}"
  - Error detection: JSON response {"status": "error"}
  - Model detection: GET /about → HardwareVersion / DeviceID field
  - Discovery: parallel HTTP subnet scan on port 8080
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

import requests

from core.exceptions import (
    CameraConnectionError,
    CameraDiscoveryError,
    CameraResponseError,
)
from core.interfaces import CameraProtocol
from core.models import DiscoveredCamera

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = 3.0
_DEFAULT_PORT = "8080"


class BirdDogTransport(CameraProtocol):
    """
    Transport implementation for BirdDog PTZ cameras (REST/JSON API).

    Command encoding for send_command():
      GET  query:   "GET /birddogcmsetup"
      POST command: "POST /birddogcmsetup {\"BlueGain\": \"32\", ...}"
    """

    # -----------------------------------------------------------------------
    # CameraProtocol — default_port
    # -----------------------------------------------------------------------

    @property
    def default_port(self) -> str:
        return _DEFAULT_PORT

    # -----------------------------------------------------------------------
    # CameraProtocol — send_command
    # -----------------------------------------------------------------------

    def send_command(self, ip: str, port: str, command: str) -> str:
        """
        Sends a command to the camera.

        GET:  "GET /birddogcmsetup"
              → GET http://<ip>:<port>/birddogcmsetup
        POST: "POST /birddogcmsetup {\"BlueGain\": \"32\", ...}"
              → POST http://<ip>:<port>/birddogcmsetup with JSON body

        Raises:
            CameraConnectionError  — network error or timeout
            CameraResponseError    — HTTP status != 200
        """
        parts = command.split(" ", 2)
        method = parts[0].upper()
        path = parts[1] if len(parts) > 1 else "/"
        body_str = parts[2] if len(parts) > 2 else None

        url = f"http://{ip}:{port}{path}"
        logger.info(f"HTTP CMD: {method} {url}")

        try:
            if method == "GET":
                response = requests.get(
                    url,
                    timeout=_DEFAULT_TIMEOUT,
                    headers={"Accept": "application/json"},
                )
            else:
                body = json.loads(body_str) if body_str else {}
                response = requests.post(
                    url,
                    json=body,
                    timeout=_DEFAULT_TIMEOUT,
                )
        except requests.exceptions.Timeout as exc:
            logger.error(f"HTTP RESP: timeout for {url}")
            raise CameraConnectionError(f"Timeout connecting to {ip}:{port}") from exc
        except requests.exceptions.ConnectionError as exc:
            logger.error(f"HTTP RESP: connection error for {url}: {exc}")
            raise CameraConnectionError(f"Cannot connect to {ip}:{port}: {exc}") from exc
        except requests.exceptions.RequestException as exc:
            logger.error(f"HTTP RESP: request error for {url}: {exc}")
            raise CameraConnectionError(f"Request failed for {ip}:{port}: {exc}") from exc

        body_text = (response.text or "").strip()
        logger.info(f"HTTP RESP: status={response.status_code} body={body_text[:200]}")

        if response.status_code != 200:
            raise CameraResponseError(
                f"HTTP {response.status_code} from {ip}:{port}",
                status_code=response.status_code,
                body=body_text,
            )

        return body_text

    # -----------------------------------------------------------------------
    # CameraProtocol — detect_model
    # -----------------------------------------------------------------------

    def detect_model(self, response: str) -> str | None:
        """
        Extracts the model ID from a /about response body.

        BirdDog /about returns JSON. Tries common field names in order:
          DeviceID, Model, model, ProductID
        """
        if not response:
            return None
        try:
            data = json.loads(response)
            for field in ("DeviceID", "Model", "model", "ProductID", "HardwareVersion"):
                val = data.get(field)
                if val:
                    return str(val).strip()
        except (json.JSONDecodeError, TypeError, AttributeError):
            pass
        return None

    # -----------------------------------------------------------------------
    # CameraProtocol — is_error
    # -----------------------------------------------------------------------

    def is_error(self, response: str) -> bool:
        """
        True if the response body signals a BirdDog API error.

        BirdDog error format: JSON with {"status": "error"} or non-empty "error" field.
        """
        if not response:
            return False
        try:
            data = json.loads(response)
            if isinstance(data, dict):
                return data.get("status") == "error" or bool(data.get("error"))
        except (json.JSONDecodeError, TypeError):
            pass
        return False

    # -----------------------------------------------------------------------
    # CameraProtocol — build_query
    # -----------------------------------------------------------------------

    def build_query(self, key: str) -> str:
        """
        Builds the GET command string for a query key.

        key = path from UI_FEATURE_QUERIES / UI_DROPDOWN_QUERIES,
              e.g. "/birddogcmsetup"

        Returns: "GET /birddogcmsetup" — passed directly to send_command().
        """
        return f"GET {key}"

    # -----------------------------------------------------------------------
    # CameraProtocol — discover
    # -----------------------------------------------------------------------

    def discover(self, timeout: float = 2.5) -> list[DiscoveredCamera]:
        """
        BirdDog subnet scan: probes every host in the local /24 subnet on
        port 8080 with GET /about. Hosts that return valid BirdDog JSON are
        returned as discovered cameras.

        Uses a thread pool for parallel probing. Per-host timeout is 0.5 s,
        so a full /24 scan completes in roughly 1-2 s.
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed
        from smart_reset.discovery import get_local_ipv4s
        import ipaddress

        local_ips = get_local_ipv4s()
        if not local_ips:
            logger.warning("BirdDog scan: no local IPv4 address found.")
            return []

        # Collect all /24 subnets reachable from local interfaces (deduplicated)
        seen_networks: set[str] = set()
        targets: list[str] = []
        for local_ip in local_ips:
            try:
                net = ipaddress.ip_network(f"{local_ip}/24", strict=False)
            except ValueError:
                continue
            net_str = str(net)
            if net_str in seen_networks:
                continue
            seen_networks.add(net_str)
            targets.extend(str(h) for h in net.hosts())

        if not targets:
            return []

        logger.info(f"BirdDog scan: probing {len(targets)} hosts on port {_DEFAULT_PORT}...")

        _probe_timeout = 0.5

        def _probe(ip: str) -> DiscoveredCamera | None:
            try:
                resp = requests.get(
                    f"http://{ip}:{_DEFAULT_PORT}/about",
                    timeout=_probe_timeout,
                    headers={"Accept": "application/json"},
                )
            except Exception:
                return None
            if resp.status_code != 200:
                return None
            body = (resp.text or "").strip()
            model = self.detect_model(body)
            if not model:
                return None
            return DiscoveredCamera(
                label=f"{model} ({ip}:{_DEFAULT_PORT})",
                model=model,
                ip=ip,
                port=_DEFAULT_PORT,
            )

        results: list[DiscoveredCamera] = []
        max_workers = min(128, len(targets))
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {pool.submit(_probe, ip): ip for ip in targets}
            for future in as_completed(futures):
                cam = future.result()
                if cam is not None:
                    results.append(cam)
                    logger.info(f"BirdDog found: {cam['model']} at {cam['ip']}")

        return results

    # -----------------------------------------------------------------------
    # CameraProtocol — query_camera_id
    # -----------------------------------------------------------------------

    def query_camera_id(self, ip: str, port: str) -> str | None:
        """
        Sends GET /about and returns the detected model ID.

        Always uses the BirdDog API port (8080) regardless of the port
        argument — the user-facing port (80) serves the web UI, not the API.

        Returns None if the camera is unreachable or model not detectable.
        Does not propagate exceptions.
        """
        try:
            body = self.send_command(ip, self.default_port, "GET /about")
        except Exception as exc:
            logger.error(f"BirdDog /about query failed for {ip}:{port}: {exc}")
            return None

        if self.is_error(body):
            logger.error(f"BirdDog /about returned error: {body}")
            return None

        model = self.detect_model(body)
        if not model:
            logger.warning(
                f"BirdDog /about response not recognized as model ID: '{body[:100]}'"
            )
        return model
