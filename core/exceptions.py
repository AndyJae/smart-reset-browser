"""
core/exceptions.py — Fehler-Hierarchie für die Plugin-Architektur.

Alle Ausnahmen erben von SmartResetError, sodass Aufrufer wahlweise
spezifische Typen oder den Basis-Typ fangen können.

Hierarchie:

  SmartResetError
  ├── CameraError                 — Basis für alle Kamera-Kommunikationsfehler
  │   ├── CameraConnectionError   — Netzwerkfehler, Timeout
  │   ├── CameraResponseError     — HTTP-Status != 200
  │   └── CameraDiscoveryError    — Discovery-Socket- oder Netzwerkfehler
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


class CameraDiscoveryError(CameraError):
    """
    Fehler während der UDP-Netzwerk-Discovery.

    Wird ausgelöst bei Socket-Fehler, fehlenden Netzwerkinterfaces oder
    wenn der Discovery-Socket nicht gebunden werden kann.
    """


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
