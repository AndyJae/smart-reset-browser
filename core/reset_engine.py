"""
core/reset_engine.py — Reset-Sequenzlogik für die Plugin-Architektur.

Ersetzt langfristig smart_reset/reset_worker.py.

Unterschiede zu reset_worker.py:
  - Nutzt CameraProtocol.send_command() statt http_client.send_command() direkt
  - Nutzt ResetResult / ResetContext aus core/models.py statt plain dict / SimpleNamespace
  - Wirft StaleSessionError statt still abzubrechen
  - Fehler aus dem Transport (CameraConnectionError, CameraCommandError) werden
    explizit gefangen und als fehlgeschlagene Schritte ins ResetResult geschrieben

Aufruf (in ThreadPoolExecutor, nie direkt im asyncio-Event-Loop):

    engine = ResetEngine(
        module=module,
        transport=transport,
        session=session,
        session_id=session_id,
        ip=ip,
        port=port,
    )
    result = engine.run()
"""

from __future__ import annotations

import logging
import time
from types import ModuleType
from typing import TYPE_CHECKING, Optional

from core.exceptions import (
    CameraCommandError,
    CameraConnectionError,
    CameraError,
    StaleSessionError,
)
from core.models import ResetContext, ResetResult

if TYPE_CHECKING:
    from core.interfaces import CameraProtocol
    from smart_reset.camera_state import CameraSession


logger = logging.getLogger(__name__)

_PANASONIC_ERROR_PREFIXES = ("ER1:", "ER2:", "ER3:")


class ResetEngine:
    """
    Führt eine vollständige Reset-Sequenz für eine Kamera durch.

    Wird einmalig pro Reset-Vorgang instanziiert. Alle Methoden sind synchron
    und müssen im ThreadPoolExecutor laufen.
    """

    def __init__(
        self,
        module: ModuleType,
        transport: "CameraProtocol",
        session: "CameraSession",
        session_id: int,
        ip: str,
        port: str,
    ) -> None:
        self._module = module
        self._transport = transport
        self._session = session
        self._session_id = session_id
        self._ip = ip
        self._port = port
        self._result = ResetResult()

    # -----------------------------------------------------------------------
    # Public entry point
    # -----------------------------------------------------------------------

    def run(self) -> ResetResult:
        """
        Führt Pre-Reset → Reset → Post-Reset durch.

        Gibt immer ein ResetResult zurück — auch bei Ausnahmen.
        Setzt session.reset_in_progress = False im finally-Block.
        """
        module_name = getattr(self._module, "DISPLAY_NAME", self._module.__name__)
        try:
            self._guard()

            self._apply_pre_reset_state()

            run_reset_fn = getattr(self._module, "run_reset", None)
            if callable(run_reset_fn):
                context = self._build_context()
                run_reset_fn(context)
            else:
                self._default_reset()

            if self._result.failed:
                logger.warning("Applying post-reset state despite reset command errors.")
            self._apply_post_reset_state()

        except StaleSessionError as exc:
            self._result.failed.append(f"Session became stale: {exc}")
            logger.warning(str(exc))
        except Exception as exc:
            self._result.failed.append(f"Worker exception: {exc}")
            logger.exception("ResetEngine.run() failed unexpectedly")
        finally:
            self._session.reset_in_progress = False
            if self._result.failed:
                logger.error(
                    f"Reset finished with errors for {module_name}: "
                    f"{len(self._result.failed)} failed, "
                    f"{self._result.successful} successful."
                )
                for item in self._result.failed:
                    logger.error(f"Reset failure detail: {item}")
            else:
                logger.info(
                    f"Reset sequence completed successfully "
                    f"({self._result.successful} commands)."
                )

        return self._result

    # -----------------------------------------------------------------------
    # Session guard
    # -----------------------------------------------------------------------

    def _guard(self) -> None:
        """Wirft StaleSessionError wenn die Session nicht mehr aktiv ist."""
        s = self._session
        if (
            not s.connected
            or s.session_id != self._session_id
            or s.ip != self._ip
            or s.port != self._port
        ):
            raise StaleSessionError(self._session_id, s.session_id)

    # -----------------------------------------------------------------------
    # Transport-Wrapper
    # -----------------------------------------------------------------------

    def _send(self, command: str) -> Optional[str]:
        """
        Sendet einen Befehl über den Transport. Gibt den Response-Body zurück.

        Fängt alle CameraError-Ausnahmen — gibt None zurück und loggt den Fehler.
        Aufrufer müssen None als Fehler behandeln.
        """
        try:
            return self._transport.send_command(self._ip, self._port, command)
        except CameraConnectionError as exc:
            logger.error(f"Connection error: {exc}")
            return None
        except CameraCommandError as exc:
            logger.error(f"Camera command error [{exc.error_code}]: {exc}")
            return None
        except CameraError as exc:
            logger.error(f"Camera error: {exc}")
            return None

    def _is_response_ok(self, body: Optional[str]) -> bool:
        """True wenn body weder None noch ein Fehler-Prefix ist."""
        if body is None:
            return False
        return not body.startswith(_PANASONIC_ERROR_PREFIXES)

    def _query(self, command: Optional[str]) -> Optional[str]:
        """Sendet einen Query-Befehl und gibt den Body zurück, oder None bei Fehler."""
        if not command:
            return None
        body = self._send(command)
        if not self._is_response_ok(body):
            return None
        return body

    # -----------------------------------------------------------------------
    # Default reset (RESET_COMMANDS durchlaufen)
    # -----------------------------------------------------------------------

    def _default_reset(self) -> None:
        commands = getattr(self._module, "RESET_COMMANDS", [])
        for label, cmd, addr, data in commands:
            self._apply_mapped_command(label, cmd, addr, data)

    def _apply_mapped_command(self, label: str, cmd: str, addr: str, data: str) -> None:
        """Führt einen einzelnen RESET_COMMANDS-Eintrag aus."""
        self._guard()
        full_cmd = f"cmd={cmd}:{addr}:{data}&res=1"
        body = self._send(full_cmd)
        if body is None:
            self._result.failed.append(f"{label}: no response")
            logger.error(f"[{label}] → no response")
            return
        if body.startswith(_PANASONIC_ERROR_PREFIXES):
            self._result.failed.append(f"{label}: {body}")
            logger.error(f"[{label}] → camera error {body}")
            return
        self._result.successful += 1
        logger.info(f"[{label}] → Set to Standard")

    # -----------------------------------------------------------------------
    # context-Objekt für run_reset()
    # -----------------------------------------------------------------------

    def _build_context(self) -> ResetContext:
        def _inc():
            self._result.successful += 1
        return ResetContext(
            default_reset=self._default_reset,
            set_value=self._apply_mapped_command,
            send_command=lambda command: self._send(command),
            logger=logger,
            record_success=_inc,
        )

    # -----------------------------------------------------------------------
    # Pre-Reset
    # -----------------------------------------------------------------------

    def _apply_pre_reset_state(self) -> None:
        for key, enabled in getattr(self._module, "PRE_RESET_FEATURE_STATES", []):
            self._guard()
            if not self._send_feature_toggle(key, enabled):
                self._result.failed.append(f"Pre-reset {key}: command failed")
                logger.warning(f"Pre-reset state could not be applied for '{key}'.")
                continue
            self._session.feature_states[key] = enabled

    # -----------------------------------------------------------------------
    # Post-Reset
    # -----------------------------------------------------------------------

    def _apply_post_reset_state(self) -> None:
        self._guard()

        for key, enabled in getattr(self._module, "POST_RESET_FEATURE_STATES", []):
            if self._send_feature_toggle(key, enabled):
                self._session.feature_states[key] = enabled

        force_off = getattr(self._module, "POST_RESET_FORCE_OFF_FEATURES", [])
        if force_off and not self._force_features_off(force_off):
            logger.error(
                f"Post-reset target state not reached: "
                f"{', '.join(force_off)} remained ON or unknown."
            )

        self._apply_dropdown_defaults()
        self._run_status_queries()

    def _apply_dropdown_defaults(self) -> None:
        dropdown_command_maps = {
            "color_temp":     self._session.c_temp_command_map,
            "gamma":          self._session.gamma_command_map,
            "linear_matrix":  self._session.lmatrix_command_map,
        }
        for dropdown_key, label in getattr(
            self._module, "POST_RESET_DROPDOWN_DEFAULTS", {}
        ).items():
            command_map = dropdown_command_maps.get(dropdown_key)
            if not command_map:
                continue
            command = command_map.get(label)
            if not command:
                logger.warning(
                    f"Missing dropdown command mapping for '{dropdown_key}' → '{label}'"
                )
                continue
            body = self._send(command)
            if not self._is_response_ok(body):
                continue
            if dropdown_key == "color_temp":
                self._session.c_temp_selection = label
            elif dropdown_key == "gamma":
                self._session.gamma_selection = label
            elif dropdown_key == "linear_matrix":
                self._session.lmatrix_selection = label

    def _run_status_queries(self) -> None:
        status_checks = getattr(self._module, "POST_RESET_STATUS_QUERIES", [])
        if not status_checks:
            return
        parts = []
        for label, query in status_checks:
            resp = self._query(query)
            parts.append(f"{label}={resp if resp is not None else 'UNKNOWN'}")
        logger.info("POST RESET STATUS: " + ", ".join(parts))

    # -----------------------------------------------------------------------
    # Feature-Toggle helpers
    # -----------------------------------------------------------------------

    def _send_feature_toggle(self, key: str, enabled: bool) -> bool:
        """Sendet den ON/OFF-Befehl für einen Feature-Key. Gibt True bei Erfolg."""
        ui_buttons = getattr(self._module, "UI_BUTTONS", {})
        entry = ui_buttons.get(key)
        if not isinstance(entry, dict):
            logger.warning(f"No UI_BUTTONS entry for key '{key}'.")
            return False
        command = entry.get("on" if enabled else "off")
        if not command:
            logger.warning(
                f"Missing '{'on' if enabled else 'off'}' command for UI_BUTTONS['{key}']."
            )
            return False
        body = self._send(f"cmd={command}&res=1")
        return self._is_response_ok(body)

    def _extract_on_off(self, response_text: str) -> Optional[bool]:
        """Liest ON/OFF-Zustand aus Response-Body (Format: 'XYZ:1' oder 'XYZ:0')."""
        if ":" not in response_text:
            return None
        value = response_text.rsplit(":", 1)[-1].strip().upper()
        if value == "1":
            return True
        if value == "0":
            return False
        return None

    def _force_features_off(
        self, feature_keys: list[str], max_attempts: int = 6
    ) -> bool:
        """
        Stellt sicher dass alle angegebenen Features OFF sind.

        Sendet nach jedem fehlgeschlagenen Versuch erneut den OFF-Befehl.
        Gibt True zurück wenn alle Features OFF sind, False nach max_attempts.
        """
        feature_queries = getattr(self._module, "UI_FEATURE_QUERIES", {})
        missing = [k for k in feature_keys if k not in feature_queries]
        if missing:
            logger.warning(
                f"Cannot enforce OFF state — missing feature queries: "
                f"{', '.join(missing)}"
            )
            return False

        for attempt in range(1, max_attempts + 1):
            self._guard()
            states: dict[str, Optional[bool]] = {}
            for key in feature_keys:
                body = self._query(feature_queries.get(key))
                states[key] = self._extract_on_off(body) if body else None

            if all(state is False for state in states.values()):
                for key in feature_keys:
                    self._session.feature_states[key] = False
                return True

            for key in feature_keys:
                self._send_feature_toggle(key, False)

            state_parts = ", ".join(
                f"{k}={'ON' if v is True else ('OFF' if v is False else 'UNKNOWN')}"
                for k, v in states.items()
            )
            logger.warning(
                f"OFF enforcement retry {attempt}/{max_attempts}: {state_parts}"
            )
            if attempt < max_attempts:
                time.sleep(0.25)

        return False
