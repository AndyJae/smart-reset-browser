"""
core/models.py — Typisierte Datenstrukturen für die Plugin-Architektur.

Drei Typen:
  DiscoveredCamera  — TypedDict für eine per Discovery gefundene Kamera
  ResetResult       — Dataclass für das Ergebnis einer Reset-Sequenz
  ResetContext       — Klasse für das context-Objekt, das an run_reset() übergeben wird
"""

from __future__ import annotations

import logging
import logging as _logging_module
from dataclasses import dataclass, field
from typing import Callable, Optional, TypedDict


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------

class DiscoveredCamera(TypedDict):
    """
    Eine per UDP-Discovery gefundene Kamera.

    Rückgabeformat von CameraProtocol.discover() und format_discovered_cameras().
    Wird als plain dict weiterverwendet — TypedDict ist zur Laufzeit ein dict.

    Felder:
        label   — Anzeigetext für UI, z. B. "AW-UE160 (192.168.0.10:80)"
        model   — Modellbezeichnung, z. B. "AW-UE160"
        ip      — IPv4-Adresse als String, z. B. "192.168.0.10"
        port    — HTTP-Port als String, z. B. "80"
    """
    label: str
    model: str
    ip: str
    port: str


# ---------------------------------------------------------------------------
# Reset-Ergebnis
# ---------------------------------------------------------------------------

@dataclass
class ResetResult:
    """
    Ergebnis einer abgeschlossenen Reset-Sequenz.

    Wird von run_reset_worker() zurückgegeben und als WebSocket-Event
    {"type": "reset_done", "status": ..., "ok": N, "failed": N} gesendet.

    Felder:
        successful  — Anzahl erfolgreich ausgeführter Befehle
        failed      — Liste fehlgeschlagener Schritte mit Beschreibung
    """
    successful: int = 0
    failed: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """True wenn kein einziger Schritt fehlgeschlagen ist."""
        return len(self.failed) == 0

    def to_ws_event(self) -> dict:
        """Serialisiert das Ergebnis als WebSocket-Event-Dict."""
        return {
            "type": "reset_done",
            "status": "ok" if self.ok else "error",
            "ok": self.successful,
            "failed": len(self.failed),
        }


# ---------------------------------------------------------------------------
# Reset-Context
# ---------------------------------------------------------------------------

class ResetContext:
    """
    Kontext-Objekt, das an run_reset(context) in Kameramodulen übergeben wird.

    Ersetzt SimpleNamespace mit typisierten Feldern. Das Interface ist identisch
    zur Desktop-Version — bestehende run_reset()-Implementierungen bleiben
    ohne Änderung kompatibel.

    Felder:
        default_reset   — führt alle RESET_COMMANDS des Moduls der Reihe nach aus
        set_value       — führt einen einzelnen Befehl aus: (label, cmd, addr, data)
        send_command    — sendet einen rohen CGI-Befehlsstring, gibt Response-Body zurück
        logging         — Standard-logging-Modul (identisch zu Desktop-Version)

    Verwendung in einem Kameramodul:
        def run_reset(context):
            context.default_reset()
            context.set_value("MY PARAM", "OSL", "FF", "80")
            context.send_command("cmd=XYZ:00:01&res=1")
            context.logging.info("Custom step done.")
    """

    def __init__(
        self,
        default_reset: Callable[[], None],
        set_value: Callable[[str, str, str, str], None],
        send_command: Callable[[str], Optional[str]],
        logger: _logging_module.Logger | None = None,
        record_success: Callable[[], None] | None = None,
    ):
        self.default_reset = default_reset
        self.set_value = set_value
        self.send_command = send_command
        # Expose as `logging` to match the SimpleNamespace interface used in existing modules.
        self.logging: _logging_module.Logger = logger or logging.getLogger(__name__)
        self._record_success: Callable[[], None] = record_success or (lambda: None)

    def record_success(self) -> None:
        """Increments the successful command counter in the ResetResult."""
        self._record_success()
