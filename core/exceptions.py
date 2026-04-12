"""
core/exceptions.py — Fehler-Hierarchie für die Plugin-Architektur.

Alle Ausnahmen erben von SmartResetError, sodass Aufrufer wahlweise
spezifische Typen oder den Basis-Typ fangen können.

Hierarchie:

  SmartResetError
  ├── CameraError                 — Basis für alle Kamera-Kommunikationsfehler
  │   ├── CameraConnectionError   — Netzwerkfehler, Timeout
  │   ├── CameraResponseError     — HTTP-Status != 200
  │   ├── CameraCommandError      — Kamera meldet ER1:/ER2:/ER3: (Protokoll-Fehler)
  │   └── CameraDiscoveryError    — Discovery-Socket- oder Netzwerkfehler
  ├── PluginError                 — Basis für Plugin-System-Fehler
  │   ├── PluginNotFoundError     — kein Modul für erkannte Modell-ID registriert
  │   └── PluginLoadError         — Modul konnte nicht importiert/geladen werden
  └── SessionError                — Basis für Session-Zustandsfehler
      └── StaleSessionError       — session_id stimmt nicht mehr überein
"""


class SmartResetError(Exception):
    """Basis-Ausnahme für alle smart-reset-eigenen Fehler."""


# ---------------------------------------------------------------------------
# Kamera-Kommunikationsfehler
# ---------------------------------------------------------------------------

class CameraError(SmartResetError):
    """Basis für alle Fehler bei der Kommunikation mit einer Kamera."""


class CameraConnectionError(CameraError):
    """
    Netzwerkfehler oder Timeout beim Verbindungsaufbau.

    Wird ausgelöst wenn die HTTP-Anfrage gar nicht erst die Kamera erreicht
    (kein Host, Timeout, Verbindung abgelehnt).

    Wrapping-Konvention:
        raise CameraConnectionError("...") from original_exc
    """


class CameraResponseError(CameraError):
    """
    Die Kamera hat geantwortet, aber mit einem unerwarteten HTTP-Status.

    Attribute:
        status_code  — HTTP-Statuscode der Antwort
        body         — Response-Body als String (kann leer sein)
    """

    def __init__(self, message: str, status_code: int, body: str = ""):
        super().__init__(message)
        self.status_code = status_code
        self.body = body


class CameraCommandError(CameraError):
    """
    Die Kamera hat den Befehl abgelehnt (Protokoll-Fehler).

    Panasonic:  Response beginnt mit "ER1:", "ER2:" oder "ER3:"
    BirdDog:    JSON mit {"status": "error"}

    Attribute:
        error_code   — herstellerspezifischer Fehlercode ("ER1", "ER2", …)
        response     — vollständiger Response-Body
    """

    def __init__(self, message: str, error_code: str = "", response: str = ""):
        super().__init__(message)
        self.error_code = error_code
        self.response = response


class CameraDiscoveryError(CameraError):
    """
    Fehler während der UDP-Netzwerk-Discovery.

    Wird ausgelöst bei Socket-Fehler, fehlenden Netzwerkinterfaces oder
    wenn der Discovery-Socket nicht gebunden werden kann.
    """


# ---------------------------------------------------------------------------
# Plugin-System-Fehler
# ---------------------------------------------------------------------------

class PluginError(SmartResetError):
    """Basis für Fehler im Plugin-Ladesystem."""


class PluginNotFoundError(PluginError):
    """
    Für die erkannte Kamera-Modell-ID ist kein Plugin registriert.

    Attribute:
        camera_id  — die erkannte Modell-ID (z. B. "AW-UE200")
    """

    def __init__(self, camera_id: str):
        super().__init__(f"No plugin registered for camera model '{camera_id}'.")
        self.camera_id = camera_id


class PluginLoadError(PluginError):
    """
    Ein Plugin-Modul konnte nicht importiert oder initialisiert werden.

    Attribute:
        module_name  — Name des fehlgeschlagenen Moduls
    """

    def __init__(self, module_name: str, reason: str = ""):
        msg = f"Failed to load plugin module '{module_name}'."
        if reason:
            msg += f" Reason: {reason}"
        super().__init__(msg)
        self.module_name = module_name


# ---------------------------------------------------------------------------
# Session-Fehler
# ---------------------------------------------------------------------------

class SessionError(SmartResetError):
    """Basis für Fehler im Zusammenhang mit dem Session-Zustand."""


class StaleSessionError(SessionError):
    """
    Der Worker läuft mit einer veralteten session_id.

    Wird ausgelöst wenn ein Worker-Thread merkt, dass die Kamera zwischenzeitlich
    getrennt oder neu verbunden wurde (session_id stimmt nicht mehr überein).

    Reset- und Balance-Worker prüfen dies vor jeder State-Mutation.
    """

    def __init__(self, expected: int, actual: int):
        super().__init__(
            f"Session is stale (expected session_id={expected}, got {actual})."
        )
        self.expected = expected
        self.actual = actual
