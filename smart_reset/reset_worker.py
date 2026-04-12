"""Reset worker — runs in a ThreadPoolExecutor, no UI dependencies."""

import logging
import time
from types import SimpleNamespace
from typing import Optional

from smart_reset.camera_state import CameraSession
from smart_reset.http_client import send_command


# ---------------------------------------------------------------------------
# Session guard
# ---------------------------------------------------------------------------

def is_session_active(session: CameraSession, session_id: int, ip: str, port: str) -> bool:
    return (
        session.connected
        and session.session_id == session_id
        and session.ip == ip
        and session.port == port
    )


# ---------------------------------------------------------------------------
# Feature-toggle helpers (derived from V23 _send_feature_toggle_command)
# ---------------------------------------------------------------------------

def _get_button_command(module, key: str, state_key: Optional[str] = None) -> Optional[str]:
    ui_buttons = getattr(module, "UI_BUTTONS", {})
    entry = ui_buttons.get(key)
    if isinstance(entry, dict):
        if state_key:
            return entry.get(state_key)
        return entry.get("cmd")
    if state_key is None and isinstance(entry, str):
        return entry
    return None


def _send_ui_command(command: Optional[str], ip: str, port: str):
    if not command:
        logging.warning("Missing UI command mapping for selected camera type.")
        return None
    return send_command(f"cmd={command}&res=1", ip, port)


def send_feature_toggle(module, key: str, enabled: bool, ip: str, port: str) -> bool:
    command = _get_button_command(module, key, "on" if enabled else "off")
    response = _send_ui_command(command, ip, port)
    if not response or response.status_code != 200:
        return False
    body = (response.text or "").strip()
    if body.startswith(("ER1:", "ER2:", "ER3:")):
        return False
    return True


def _extract_on_off(response_text: str) -> Optional[bool]:
    if ":" not in response_text:
        return None
    value = response_text.rsplit(":", 1)[-1].strip().upper()
    if value == "1":
        return True
    if value == "0":
        return False
    return None


def _query_command(command: Optional[str], ip: str, port: str) -> Optional[str]:
    if not command:
        return None
    response = _send_ui_command(command, ip, port)
    if response is None or response.status_code != 200:
        return None
    text = (response.text or "").strip()
    if not text or text.startswith(("ER1:", "ER2:", "ER3:")):
        return None
    return text


# ---------------------------------------------------------------------------
# Pre / Post reset state application
# ---------------------------------------------------------------------------

def apply_pre_reset_state(
    session: CameraSession,
    module,
    session_id: int,
    ip: str,
    port: str,
) -> list[str]:
    failures = []
    for key, enabled in getattr(module, "PRE_RESET_FEATURE_STATES", []):
        if not is_session_active(session, session_id, ip, port):
            return failures
        if not send_feature_toggle(module, key, enabled, ip, port):
            failures.append(f"Pre-reset {key}: command failed")
            logging.warning(f"Pre-reset state could not be applied for '{key}'.")
            continue
        session.feature_states[key] = enabled
    return failures


def _force_features_off(
    session: CameraSession,
    module,
    session_id: int,
    ip: str,
    port: str,
    feature_keys: list[str],
    max_attempts: int = 6,
) -> bool:
    feature_queries = getattr(module, "UI_FEATURE_QUERIES", {})
    if not feature_keys:
        return True
    missing = [k for k in feature_keys if k not in feature_queries]
    if missing:
        logging.warning(f"Cannot enforce OFF state for missing feature queries: {', '.join(missing)}")
        return False

    for attempt in range(1, max_attempts + 1):
        if not is_session_active(session, session_id, ip, port):
            return False
        states = {}
        for key in feature_keys:
            response_text = _query_command(feature_queries.get(key), ip, port)
            states[key] = _extract_on_off(response_text) if response_text else None

        if all(state is False for state in states.values()):
            for key in feature_keys:
                session.feature_states[key] = False
            return True

        for key in feature_keys:
            send_feature_toggle(module, key, False, ip, port)

        state_parts = ", ".join(
            f"{k}={'ON' if v is True else ('OFF' if v is False else 'UNKNOWN')}"
            for k, v in states.items()
        )
        logging.warning(f"OFF enforcement retry {attempt}/{max_attempts}: {state_parts}")

    return False


def apply_post_reset_state(
    session: CameraSession,
    module,
    session_id: int,
    ip: str,
    port: str,
):
    if not is_session_active(session, session_id, ip, port):
        return

    for key, enabled in getattr(module, "POST_RESET_FEATURE_STATES", []):
        if send_feature_toggle(module, key, enabled, ip, port):
            session.feature_states[key] = enabled

    force_off = getattr(module, "POST_RESET_FORCE_OFF_FEATURES", [])
    if force_off and not _force_features_off(session, module, session_id, ip, port, force_off):
        logging.error(
            f"Post-reset target state not reached: {', '.join(force_off)} remained ON or unknown."
        )

    dropdown_command_maps = {
        "color_temp": session.c_temp_command_map,
        "gamma": session.gamma_command_map,
        "linear_matrix": session.lmatrix_command_map,
    }
    for dropdown_key, label in getattr(module, "POST_RESET_DROPDOWN_DEFAULTS", {}).items():
        command_map = dropdown_command_maps.get(dropdown_key)
        if not command_map:
            continue
        command = command_map.get(label)
        if not command:
            logging.warning(f"Missing dropdown command mapping for '{dropdown_key}' -> '{label}'")
            continue
        response = _send_ui_command(command, ip, port)
        if not response or response.status_code != 200:
            continue
        body = (response.text or "").strip()
        if body.startswith(("ER1:", "ER2:", "ER3:")):
            continue
        if dropdown_key == "color_temp":
            session.c_temp_selection = label
        elif dropdown_key == "gamma":
            session.gamma_selection = label
        elif dropdown_key == "linear_matrix":
            session.lmatrix_selection = label

    status_checks = getattr(module, "POST_RESET_STATUS_QUERIES", [])
    if status_checks:
        parts = []
        for label, query in status_checks:
            resp = _query_command(query, ip, port)
            parts.append(f"{label}={resp if resp is not None else 'UNKNOWN'}")
        logging.info("POST RESET STATUS: " + ", ".join(parts))


# ---------------------------------------------------------------------------
# Main reset worker — call via loop.run_in_executor(None, run_reset_worker, ...)
# ---------------------------------------------------------------------------

def run_reset_worker(
    session: CameraSession,
    module,
    session_id: int,
    ip: str,
    port: str,
) -> dict:
    """Execute the full reset sequence. Returns {"successful": int, "failed": list[str]}."""
    commands = getattr(module, "RESET_COMMANDS", [])
    module_name = getattr(module, "DISPLAY_NAME", "Unknown")
    failed: list[str] = []
    successful = 0

    try:
        if not is_session_active(session, session_id, ip, port):
            return {"successful": 0, "failed": ["Session no longer active before reset started."]}

        pre_failures = apply_pre_reset_state(session, module, session_id, ip, port)
        failed.extend(pre_failures)

        def _apply_mapped_command(label: str, cmd: str, addr: str, data: str):
            nonlocal successful
            if not is_session_active(session, session_id, ip, port):
                raise RuntimeError("Session is no longer active.")
            full_cmd = f"cmd={cmd}:{addr}:{data}&res=1"
            response = send_command(full_cmd, ip, port)
            if response is None:
                failed.append(f"{label}: no HTTP response")
                logging.error(f"[{label}] -> no HTTP response")
                return
            if response.status_code != 200:
                failed.append(f"{label}: HTTP {response.status_code}")
                logging.error(f"[{label}] -> HTTP {response.status_code}")
                return
            body = (response.text or "").strip()
            if body.startswith(("ER1:", "ER2:", "ER3:")):
                failed.append(f"{label}: {body}")
                logging.error(f"[{label}] -> camera error {body}")
                return
            successful += 1
            logging.info(f"[{label}] -> Set to Standard")

        def _default_reset():
            for label, cmd, addr, data in commands:
                _apply_mapped_command(label, cmd, addr, data)

        run_reset_fn = getattr(module, "run_reset", None)
        if callable(run_reset_fn):
            context = SimpleNamespace(
                default_reset=_default_reset,
                set_value=_apply_mapped_command,
                send_command=lambda command: send_command(command, ip, port),
                logging=logging,
            )
            run_reset_fn(context)
        else:
            _default_reset()

        if failed:
            logging.warning("Applying post-reset target state despite reset command errors.")
        apply_post_reset_state(session, module, session_id, ip, port)

    except Exception as exc:
        failed.append(f"Worker exception: {exc}")
        logging.exception("Reset worker failed")
    finally:
        if failed:
            logging.error(
                f"Reset finished with errors for {module_name}: "
                f"{len(failed)} failed, {successful} successful."
            )
            for item in failed:
                logging.error(f"Reset failure detail: {item}")
        else:
            logging.info(f"Reset sequence completed successfully ({successful} commands).")
        session.reset_in_progress = False

    return {"successful": successful, "failed": failed}
