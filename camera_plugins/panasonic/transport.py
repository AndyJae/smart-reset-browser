"""
camera_plugins/panasonic/transport.py — Panasonic CGI Transport-Implementierung.

Implementiert CameraProtocol für das Panasonic CGI-Protokoll:
  - HTTP GET auf /cgi-bin/aw_cam?<command>
  - Fehlerformat: Response beginnt mit ER1:, ER2:, ER3:
  - Modell-Erkennung: Regex (AW|AK)-[A-Z0-9]+ auf QID-Antwort (z. B. AW-UE160, AK-UB300)
  - Discovery: UDP-Broadcast (delegiert an smart_reset/discovery.py)

Für Discovery wird der bestehende Code in smart_reset/discovery.py wiederverwendet —
kein Neuschreiben der komplexen UDP-Logik.
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

import requests

from core.exceptions import (
    CameraCommandError,
    CameraConnectionError,
    CameraDiscoveryError,
    CameraResponseError,
)
from core.interfaces import CameraProtocol
from core.models import DiscoveredCamera
from smart_reset.discovery import (
    create_discovery_socket,
    discover_cameras,
    format_discovered_cameras,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

_MODEL_REGEX = re.compile(r"(?:AW|AK)-[A-Z0-9]+")
_ERROR_PREFIXES = ("ER1:", "ER2:", "ER3:")
_DEFAULT_TIMEOUT = 3.0


class PanasonicTransport(CameraProtocol):
    """
    Transport-Implementierung für Panasonic PTZ-Kameras (CGI-Protokoll).

    Zustandslos — kann als Singleton für alle Panasonic-Kameras verwendet werden.
    """

    # -----------------------------------------------------------------------
    # CameraProtocol — send_command
    # -----------------------------------------------------------------------

    def send_command(self, ip: str, port: str, command: str) -> str:
        """
        Sendet einen CGI-Befehl an die Kamera.

        URL: GET http://<ip>:<port>/cgi-bin/aw_cam?<command>

        Gibt den Response-Body (stripped) zurück.

        Wirft:
            CameraConnectionError  — Netzwerkfehler oder Timeout
            CameraResponseError    — HTTP-Status != 200
        """
        url = f"http://{ip}:{port}/cgi-bin/aw_cam?{command}"
        logger.info(f"HTTP CMD: GET {url}")
        try:
            response = requests.get(url, timeout=_DEFAULT_TIMEOUT)
        except requests.exceptions.Timeout as exc:
            logger.error(f"HTTP RESP: timeout for {url}")
            raise CameraConnectionError(
                f"Timeout connecting to {ip}:{port}"
            ) from exc
        except requests.exceptions.ConnectionError as exc:
            logger.error(f"HTTP RESP: connection error for {url}: {exc}")
            raise CameraConnectionError(
                f"Cannot connect to {ip}:{port}: {exc}"
            ) from exc
        except requests.exceptions.RequestException as exc:
            logger.error(f"HTTP RESP: request error for {url}: {exc}")
            raise CameraConnectionError(
                f"Request failed for {ip}:{port}: {exc}"
            ) from exc

        body = (response.text or "").strip().replace("\r", "\\r").replace("\n", "\\n")
        logger.info(f"HTTP RESP: status={response.status_code} body={body}")

        if response.status_code != 200:
            raise CameraResponseError(
                f"HTTP {response.status_code} from {ip}:{port}",
                status_code=response.status_code,
                body=body,
            )

        return body

    # -----------------------------------------------------------------------
    # CameraProtocol — detect_model
    # -----------------------------------------------------------------------

    def detect_model(self, response: str) -> str | None:
        """
        Extrahiert die Modellbezeichnung aus einem QID-Response-Body.

        Panasonic QID-Antwort enthält die Modellbezeichnung als Token
        nach dem Muster (AW|AK)-[A-Z0-9]+ (z. B. "AW-UE160", "AW-UE150A", "AK-UB300").

        Gibt None zurück wenn kein passendes Token gefunden wird.
        """
        if not response:
            return None
        match = _MODEL_REGEX.search(response)
        return match.group(0) if match else None

    # -----------------------------------------------------------------------
    # CameraProtocol — is_error
    # -----------------------------------------------------------------------

    def is_error(self, response: str) -> bool:
        """
        True wenn der Response-Body einen Panasonic-Fehler signalisiert.

        Panasonic-Fehlerformat: Response beginnt mit ER1:, ER2:, oder ER3:.
          ER1: Syntax-Fehler
          ER2: Befehl außerhalb des erlaubten Bereichs
          ER3: Kamera im falschen Zustand für diesen Befehl
        """
        return bool(response) and response.startswith(_ERROR_PREFIXES)

    # -----------------------------------------------------------------------
    # CameraProtocol — build_query
    # -----------------------------------------------------------------------

    def build_query(self, key: str) -> str:
        """
        Baut den vollständigen CGI-Query-String aus einem Befehlsfragment.

        key = Befehlsfragment aus UI_FEATURE_QUERIES / UI_DROPDOWN_QUERIES,
              z. B. "QSE" oder "QAF"

        Ergebnis: "cmd=QSE&res=1" — direkt als command an send_command() übergeben.
        """
        return f"cmd={key}&res=1"

    def build_command(self, cmd: str) -> str:
        """
        Baut den vollständigen CGI-Set-Befehl aus einem Befehlsfragment.

        cmd = Befehlsfragment aus UI_BUTTONS / UI_DROPDOWNS,
              z. B. "OSA:11:1" oder "OAW:0"

        Ergebnis: "cmd=OSA:11:1&res=1" — direkt als command an send_command() übergeben.
        """
        return f"cmd={cmd}&res=1"

    # -----------------------------------------------------------------------
    # CameraProtocol — discover
    # -----------------------------------------------------------------------

    def discover(self, timeout: float = 2.5) -> list[DiscoveredCamera]:
        """
        Führt eine Panasonic UDP-Discovery durch.

        Delegiert an smart_reset/discovery.py — kein Neuschreiben der
        komplexen UDP- und Netzwerk-Interface-Logik.

        Erstellt und schließt den Discovery-Socket selbst.

        Gibt eine Liste von DiscoveredCamera-Dicts zurück (kann leer sein).
        Wirft CameraDiscoveryError bei Socket-Fehler.
        """
        sock = create_discovery_socket()
        if sock is None:
            raise CameraDiscoveryError(
                "Could not create Panasonic discovery socket."
            )
        try:
            configs = discover_cameras(sock)
        except Exception as exc:
            raise CameraDiscoveryError(
                f"Panasonic UDP discovery failed: {exc}"
            ) from exc
        finally:
            try:
                sock.close()
            except OSError:
                pass

        return format_discovered_cameras(configs)

    # -----------------------------------------------------------------------
    # Hilfsmethoden (Panasonic-spezifisch, nicht Teil des Interface)
    # -----------------------------------------------------------------------

    def query_camera_id(self, ip: str, port: str) -> str | None:
        """
        Sendet QID-Abfrage und gibt die erkannte Modell-ID zurück.

        Gibt None zurück wenn keine Verbindung möglich oder Modell nicht erkennbar.
        Logt Fehler intern — wirft keine Exception nach außen.

        Ersetzt smart_reset/http_client.query_camera_id().
        """
        try:
            body = self.send_command(ip, port, "cmd=QID&res=1")
        except CameraConnectionError as exc:
            logger.error(f"QID query failed: {exc}")
            return None
        except CameraResponseError as exc:
            logger.error(f"QID query HTTP error: {exc}")
            return None

        if self.is_error(body):
            logger.error(f"QID returned camera error: {body}")
            return None

        model = self.detect_model(body)
        if not model:
            logger.warning(f"QID response not recognized as model ID: '{body}'")
        return model
