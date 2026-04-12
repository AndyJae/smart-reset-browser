"""
camera_plugins/panasonic/base.py — Gemeinsame Panasonic-Hilfslogik.

Wird von allen Panasonic-Kameramodulen in camera_plugins/panasonic/ importiert.

API-Unterschied zu camera_types/:
    context.send_command() gibt hier str | None zurück (Body direkt),
    nicht requests.Response. Die Hilfsfunktionen in dieser Datei sind
    an das neue Interface angepasst.

Typisches Verwendungsmuster in einem Kameramodul:

    from camera_plugins.panasonic.base import (
        PROTOCOL,
        query_raw, extract_value,
        send_set_command,
        ensure_feature_state, ensure_dropdown_value,
        apply_reset_commands, skip_reset_commands,
    )

    CAMERA_ID    = "AW-UE160"
    DISPLAY_NAME = "Panasonic AW-UE160"
    PROTOCOL     = PROTOCOL  # "panasonic"

    def run_reset(context):
        prep = _prepare_reset_environment(context)
        _run_reset_sequence(context, prep)
"""

from __future__ import annotations

from typing import Any, Optional

# ---------------------------------------------------------------------------
# Protokoll-Konstante
# ---------------------------------------------------------------------------

PROTOCOL: str = "panasonic"

# Fehler-Prefixe des Panasonic CGI-Protokolls
_ERROR_PREFIXES = ("ER1:", "ER2:", "ER3:")


# ---------------------------------------------------------------------------
# Query-Hilfsfunktionen
# ---------------------------------------------------------------------------

def query_raw(context: Any, query_cmd: str) -> Optional[str]:
    """
    Sendet einen Query-Befehl und gibt den Response-Body zurück.

    context.send_command() wird mit dem vollständigen CGI-String aufgerufen
    und gibt str | None zurück (neues ResetContext-Interface).

    Gibt None zurück bei:
      - Verbindungsfehler (context.send_command returns None)
      - Leerem Body
      - Panasonic-Fehlerresponse (ER1:/ER2:/ER3:)
    """
    body: Optional[str] = context.send_command(f"cmd={query_cmd}&res=1")
    if body is None:
        context.logging.warning(
            f"Reset prep: query '{query_cmd}' — no response (connection error or timeout)"
        )
        return None
    body = body.strip()
    if not body:
        context.logging.warning(
            f"Reset prep: query '{query_cmd}' returned empty body"
        )
        return None
    if body.startswith(_ERROR_PREFIXES):
        context.logging.warning(
            f"Reset prep: query '{query_cmd}' returned camera error: {body}"
        )
        return None
    return body


def extract_value(body: Optional[str]) -> Optional[str]:
    """
    Extrahiert den Wert nach dem letzten ':' aus einem Response-Body.

    Beispiel: "QSJ:D7:01" → "01",  "QAF:1" → "1"

    Gibt None zurück wenn body None ist oder kein ':' enthält.
    """
    if not body or ":" not in body:
        return None
    value = body.rsplit(":", 1)[-1].strip().upper()
    return value if value else None


# ---------------------------------------------------------------------------
# Set-Hilfsfunktionen
# ---------------------------------------------------------------------------

def send_set_command(context: Any, label: str, set_cmd: str) -> bool:
    """
    Sendet einen Set-Befehl. Gibt True bei Erfolg zurück.

    set_cmd = vollständiger CGI-Befehl ohne "cmd=" Prefix, z. B. "OSJ:56:0"
    """
    body: Optional[str] = context.send_command(f"cmd={set_cmd}&res=1")
    if body is None:
        context.logging.warning(
            f"Reset prep: '{label}' — set command '{set_cmd}' got no response"
        )
        return False
    body = body.strip()
    if body.startswith(_ERROR_PREFIXES):
        context.logging.warning(
            f"Reset prep: '{label}' — set command '{set_cmd}' returned camera error: {body}"
        )
        return False
    return True


def ensure_feature_state(
    context: Any,
    label: str,
    query_cmd: str,
    set_cmd: str,
    want_on: bool,
) -> bool:
    """
    Stellt sicher dass ein Feature ON oder OFF ist. Gibt True wenn Zielzustand erreicht.

    Ablauf:
      1. Query senden → aktuellen Zustand lesen
      2. Stimmt bereits → True
      3. Sonst set_cmd senden → erneut query → verifizieren

    want_on=True  → Zielwert "1"
    want_on=False → Zielwert "0"
    """
    wanted = "1" if want_on else "0"
    current = extract_value(query_raw(context, query_cmd))
    if current == wanted:
        return True

    action = "enabling" if want_on else "disabling"
    context.logging.info(f"Reset prep: {action} {label}")

    if not send_set_command(context, label, set_cmd):
        return False

    verified = extract_value(query_raw(context, query_cmd))
    if verified == wanted:
        return True

    context.logging.warning(
        f"Reset prep: could not verify {label} as "
        f"{'ON' if want_on else 'OFF'} after '{set_cmd}'"
    )
    return False


def ensure_dropdown_value(
    context: Any,
    label: str,
    query_cmd: str,
    set_cmd: str,
    wanted_value: str,
) -> bool:
    """
    Stellt sicher dass ein Dropdown-Wert gesetzt ist. Gibt True wenn Zielwert erreicht.

    wanted_value = Wert nach dem letzten ':', z. B. "01", "0", "3"

    Ablauf:
      1. Query senden → aktuellen Wert lesen
      2. Stimmt bereits → True
      3. Sonst set_cmd + ":" + wanted_value senden → verifizieren
    """
    target = wanted_value.strip().upper()
    current = extract_value(query_raw(context, query_cmd))
    if current == target:
        return True

    context.logging.info(f"Reset prep: setting {label} to {target}")

    if not send_set_command(context, label, f"{set_cmd}:{target}"):
        return False

    verified = extract_value(query_raw(context, query_cmd))
    if verified == target:
        return True

    context.logging.warning(
        f"Reset prep: could not verify {label}={target}"
    )
    return False


# ---------------------------------------------------------------------------
# Reset-Sequenz-Hilfsfunktionen
# ---------------------------------------------------------------------------

def apply_reset_commands(context: Any, entries: list[dict]) -> None:
    """
    Führt eine Liste von Reset-Command-Entries aus.

    Jeder Entry ist ein dict mit den Schlüsseln:
        label, cmd, addr, data
    """
    for entry in entries:
        context.set_value(entry["label"], entry["cmd"], entry["addr"], entry["data"])


def skip_reset_commands(context: Any, entries: list[dict], reason: str) -> None:
    """Loggt alle übersprungenen Reset-Command-Entries mit Begründung."""
    for entry in entries:
        context.logging.warning(f"Skipping {entry['label']}: {reason}")


def build_entries(reset_commands: list[tuple]) -> list[dict]:
    """
    Wandelt RESET_COMMANDS-Tupel in Entry-Dicts um (normalisiert auf Uppercase).

    Eingabe:  [("KNEE", "OSA", "2D", "1"), ...]
    Ausgabe:  [{"index": 0, "label": "KNEE", "cmd": "OSA", "addr": "2D", "data": "1"}, ...]
    """
    return [
        {
            "index": i,
            "label": label,
            "cmd": cmd.upper(),
            "addr": addr.upper(),
            "data": data.upper(),
        }
        for i, (label, cmd, addr, data) in enumerate(reset_commands)
    ]


def filter_entries(
    entries: list[dict],
    key_set: set[tuple[str, str]],
) -> list[dict]:
    """
    Filtert Entry-Dicts nach (cmd, addr)-Paaren.

    key_set = {("OSL", "25"), ("OSJ", "0D"), ...}
    """
    return [e for e in entries if (e["cmd"], e["addr"]) in key_set]
