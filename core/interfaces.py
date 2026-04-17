"""
core/interfaces.py — Abstrakte Basis- und Protokollklassen für die Plugin-Architektur.

Zwei Ebenen:
  CameraProtocol   — ABC für Transport-Implementierungen (Panasonic CGI, BirdDog REST, …)
  CameraModule     — typing.Protocol für Kameramodule (strukturelles Subtyping, kein ABC)

CameraProtocol wird von transport.py-Klassen in camera_plugins/ implementiert.
CameraModule beschreibt den Vertrag der Datei-Module (camera_plugins/panasonic/aw_ue160.py usw.)
— sie sind Python-Module, keine Klassen, daher nur für statische Typprüfung relevant.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Protocol, runtime_checkable


# ---------------------------------------------------------------------------
# Transport-Schicht
# ---------------------------------------------------------------------------

class CameraProtocol(ABC):
    """
    Abstrakte Basisklasse für Kamera-Transport-Implementierungen.

    Jede Hersteller-Implementierung (Panasonic, BirdDog, …) erbt von dieser
    Klasse und überschreibt alle abstrakten Methoden.

    Alle Methoden sind synchron — Aufrufer sind verantwortlich dafür, sie in
    einem ThreadPoolExecutor auszuführen (niemals direkt im asyncio-Event-Loop).
    """

    @abstractmethod
    def send_command(self, ip: str, port: str, command: str) -> str:
        """
        Sendet einen Befehl an die Kamera und gibt den Response-Body zurück.

        Panasonic:  command = "cmd=QID&res=1"  → GET /cgi-bin/aw_cam?cmd=QID&res=1
        BirdDog:    command = JSON-String       → POST /birddogptz/<resource>

        Wirft CameraConnectionError bei Netzwerkfehler oder Timeout.
        Wirft CameraResponseError wenn HTTP-Status != 200.
        Gibt niemals None zurück — leerer Response-Body wird als "" zurückgegeben.
        """
        ...

    @abstractmethod
    def detect_model(self, response: str) -> str | None:
        """
        Extrahiert die Modellbezeichnung aus dem Response-Body einer Identitäts-Abfrage.

        Panasonic:  QID-Antwort enthält "AW-UE160" → gibt "AW-UE160" zurück
        BirdDog:    REST-Response mit Modellfeld

        Gibt None zurück wenn das Modell nicht erkannt werden kann.
        """
        ...

    @abstractmethod
    def is_error(self, response: str) -> bool:
        """
        Gibt True zurück wenn der Response-Body einen Kamera-Fehler signalisiert.

        Panasonic:  Response beginnt mit "ER1:", "ER2:", "ER3:"
        BirdDog:    JSON mit {"status": "error"}
        """
        ...

    @abstractmethod
    def build_query(self, key: str) -> str:
        """
        Baut den Abfrage-Befehlsstring für einen Feature-Key.

        key entspricht einem Key aus UI_FEATURE_QUERIES oder UI_DROPDOWN_QUERIES
        im Kameramodul. Die Implementierung wandelt diesen in den
        protokollspezifischen Abfragebefehl um.
        """
        ...

    @abstractmethod
    def build_command(self, cmd: str) -> str:
        """
        Baut den vollständigen Set-Befehlsstring aus einem Befehlsfragment.

        cmd entspricht einem Wert aus UI_BUTTONS oder UI_DROPDOWNS.
        Die Implementierung wandelt diesen in den protokollspezifischen
        Befehlsstring um, der direkt an send_command() übergeben werden kann.

        Panasonic:  "OSA:11:1"  → "cmd=OSA:11:1&res=1"
        BirdDog:    already full command string → returned as-is
        """
        ...

    @abstractmethod
    def discover(self, timeout: float = 2.5) -> list[dict[str, Any]]:
        """
        Führt eine Netzwerk-Discovery durch und gibt gefundene Kameras zurück.

        Rückgabe: Liste von Dicts mit mindestens den Schlüsseln:
          - "ip":    str  — IPv4-Adresse
          - "port":  str  — HTTP-Port
          - "model": str  — Modellbezeichnung (z. B. "AW-UE160")
          - "label": str  — Anzeigetext für UI ("AW-UE160 (192.168.0.10:80)")

        Gibt eine leere Liste zurück wenn keine Kamera gefunden oder Discovery
        nicht unterstützt wird.
        """
        ...

    @property
    def default_port(self) -> str:
        """
        The default API port for this transport.

        Used to correct the session port after identification when the user
        entered a different port (e.g. 80 instead of 8080 for BirdDog).
        Override in subclasses that use a non-standard port.
        """
        return "80"

    @abstractmethod
    def query_camera_id(self, ip: str, port: str) -> "str | None":
        """
        Sends an identification query and returns the detected model ID.

        Panasonic: sends QID, extracts AW-[A-Z0-9]+ from response.
        BirdDog:   sends GET /about, extracts DeviceID from JSON response.

        Returns None if the camera is unreachable or model not detectable.
        Must not propagate exceptions — handle internally and return None.
        """
        ...


# ---------------------------------------------------------------------------
# Modul-Schicht (strukturelles Subtyping für Kameramodule)
# ---------------------------------------------------------------------------

@runtime_checkable
class CameraModule(Protocol):
    """
    Protokoll-Klasse für Kameramodule in camera_plugins/<hersteller>/.

    Kameramodule sind Python-Module (keine Klassen-Instanzen). Diese Protocol-
    Klasse dient ausschließlich der statischen Typprüfung (mypy/pyright) und
    als lesbare Spezifikation des Modulvertrags.

    Pflichtfelder:
      CAMERA_ID       — eindeutiger Bezeichner, z. B. "AW-UE160"
      DISPLAY_NAME    — Anzeigename, z. B. "Panasonic AW-UE160"
      PROTOCOL        — Transport-Protokoll: "panasonic" | "birddog"
                        Default "panasonic" — bestehende Module ohne dieses
                        Feld bleiben kompatibel.
      RESET_COMMANDS  — Liste von (label, cmd, addr, data)-Tuples für den Reset
      UI_BUTTONS      — {key: {"on": cmd, "off": cmd}} für Feature-Toggles
      UI_DROPDOWNS    — {key: [(label, cmd), …]} für Dropdown-Auswahl
      UI_FEATURE_QUERIES   — {key: query_cmd} zum Abfragen des Feature-Zustands
      UI_DROPDOWN_QUERIES  — {key: query_cmd} zum Abfragen der Dropdown-Auswahl

    Optionale Felder (werden via getattr mit Default gelesen):
      CAMERA_ID_ALIASES          — list[str]: alternative QID-Tokens für dieses Modul
      AWW_REQUIRED_OPTIONS       — list[str]: Color-Temp-Labels für AWW erlaubt
      BALANCE_COMPLETION_QUERIES — dict: Abfragen zur Balance-Fertigstellungserkennung
      BALANCE_MAX_WAIT_SECONDS   — float: Timeout für Balance-Operation
      PRE_RESET_FEATURE_STATES   — list[(key, bool)]: Feature-Zustände vor Reset
      POST_RESET_FEATURE_STATES  — list[(key, bool)]: Feature-Zustände nach Reset
      POST_RESET_FORCE_OFF_FEATURES — list[str]: Features die nach Reset OFF sein müssen
      POST_RESET_DROPDOWN_DEFAULTS  — dict[str, str]: Dropdown-Defaults nach Reset
      POST_RESET_STATUS_QUERIES     — list[(label, query)]: Statusabfragen nach Reset
      run_reset(context)         — optionale Funktion für kameraspezifischen Reset-Ablauf
    """

    CAMERA_ID: str
    DISPLAY_NAME: str
    PROTOCOL: str
    RESET_COMMANDS: list[tuple[str, str, str, str]]
    UI_BUTTONS: dict[str, dict[str, str]]
    UI_DROPDOWNS: dict[str, list[tuple[str, str]]]
    UI_FEATURE_QUERIES: dict[str, str]
    UI_DROPDOWN_QUERIES: dict[str, str]
