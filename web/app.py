"""FastAPI application — all routes."""

import asyncio
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi import FastAPI, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from camera_plugins.birddog.transport import BirdDogTransport
from camera_plugins.panasonic.base import delete_presets
from camera_plugins.panasonic.transport import PanasonicTransport
from core.exceptions import CameraDiscoveryError
from core.registry import PluginRegistry
from core.reset_engine import ResetEngine
from smart_reset.camera_state import CameraSession
from web.ws_manager import WebSocketLogHandler, manager as ws_manager

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).parent

app = FastAPI(title="smart-reset")
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

_executor = ThreadPoolExecutor(max_workers=4)

_LOG_PATH = Path.home() / "smart-reset.log"
_file_handler: logging.FileHandler | None = None


# ---------------------------------------------------------------------------
# Startup / shutdown
# ---------------------------------------------------------------------------

@app.on_event("startup")
async def on_startup():
    import sys as _sys

    loop = asyncio.get_running_loop()
    ws_manager.set_loop(loop)

    handler = WebSocketLogHandler(ws_manager)
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%H:%M:%S"))
    logging.getLogger().addHandler(handler)
    logging.getLogger().setLevel(logging.INFO)

    # When running as a PyInstaller frozen bundle pkgutil.iter_modules() cannot
    # walk the embedded archive, so we provide the full module name list explicitly.
    _frozen = getattr(_sys, "frozen", False)
    _panasonic_aw_modules = [
        "aw_he120", "aw_he130", "aw_he40", "aw_he42", "aw_he50", "aw_he60",
        "aw_hr140", "aw_ue100", "aw_ue145", "aw_ue150", "aw_ue160",
        "aw_ue30", "aw_ue40", "aw_ue50", "aw_ue70", "aw_ue80",
    ]
    _panasonic_ak_modules = ["ak_ub300"]
    _birddog_modules = ["p100", "p110", "p200", "p240", "p4k", "p_generic"]

    registry = PluginRegistry()
    registry.load_package(
        "camera_plugins.panasonic",
        module_prefix="aw_",
        frozen_names=_panasonic_aw_modules if _frozen else None,
    )
    registry.load_package(
        "camera_plugins.panasonic",
        module_prefix="ak_",
        frozen_names=_panasonic_ak_modules if _frozen else None,
    )
    registry.load_package(
        "camera_plugins.birddog",
        module_prefix="p",
        frozen_names=_birddog_modules if _frozen else None,
    )
    registry.register_transport("panasonic", PanasonicTransport())
    registry.register_transport("birddog", BirdDogTransport())
    app.state.registry = registry
    app.state.session = CameraSession()

    ids = registry.registered_camera_ids()
    display_names = sorted(set(
        getattr(registry.resolve_module(cid), "DISPLAY_NAME", cid)
        for cid in ids
    ))
    logging.info(f"Loaded {len(ids)} camera model(s): {', '.join(display_names)}")
    logging.info(f"Registered transports: {list(registry.all_transports().keys())}")

    # Load optional extension plugin
    import importlib, os as _os, sys as _sys
    _plugin_path = _os.environ.get("SMART_RESET_PLUGIN", "").strip()
    if _plugin_path:
        if _plugin_path not in _sys.path:
            _sys.path.insert(0, _plugin_path)
        try:
            _plug = importlib.import_module("matching_plugin")
            if hasattr(_plug, "router"):
                app.include_router(_plug.router)
                logging.info(f"Plugin loaded: matching_plugin from {_plugin_path}")
        except Exception as _exc:
            logging.warning(f"Plugin load skipped: {_exc}")


@app.on_event("shutdown")
async def on_shutdown():
    _executor.shutdown(wait=False)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _session(request: Request) -> CameraSession:
    return request.app.state.session


def _registry(request: Request) -> PluginRegistry:
    return request.app.state.registry


_DEFAULT_UI_LAYOUT = [
    ("knee",       "flare",   "gamma",         "gamma"),
    ("drs",        "auto_iris","auto_focus",    "color_temp"),
    ("white_clip", "matrix",  "linear_matrix", "linear_matrix"),
]

_DEFAULT_UI_BUTTONS = {
    "knee":          {"on": "", "off": ""},
    "flare":         {"on": "", "off": ""},
    "gamma":         {"on": "", "off": ""},
    "drs":           {"on": "", "off": ""},
    "auto_iris":     {"on": "", "off": ""},
    "auto_focus":    {"on": "", "off": ""},
    "white_clip":    {"on": "", "off": ""},
    "matrix":        {"on": "", "off": ""},
    "linear_matrix": {"on": "", "off": ""},
    "awb_black":     {"cmd": ""},
    "aww_white":     {"cmd": ""},
}


def _render_panel(request: Request, **extra):
    session: CameraSession = _session(request)
    module = _registry(request).resolve_module(session.camera_id)
    ui_buttons = getattr(module, "UI_BUTTONS", {}) if module else _DEFAULT_UI_BUTTONS
    ui_dropdowns = getattr(module, "UI_DROPDOWNS", {}) if module else {}

    ui_dropdowns_sync = set(getattr(module, "UI_BUTTON_DROPDOWN_SYNC", {}).keys()) if module else set()
    ui_button_labels = getattr(module, "UI_BUTTON_LABELS", {}) if module else {}
    ui_button_conditions = getattr(module, "UI_BUTTON_CONDITIONS", {}) if module else {}
    ui_dropdown_conditions = getattr(module, "UI_DROPDOWN_CONDITIONS", {}) if module else {}
    for _gate_keys in ui_dropdown_conditions.values():
        ui_dropdowns_sync.update(_gate_keys)
    ui_layout = getattr(module, "UI_LAYOUT", None) if module else None
    if ui_layout is None:
        ui_layout = _DEFAULT_UI_LAYOUT
    ui_balance_dropdown = getattr(module, "UI_BALANCE_DROPDOWN", None) if module else None
    ctx = {
        "request": request,
        "session": session,
        "ui_buttons": ui_buttons,
        "ui_dropdowns": ui_dropdowns,
        "ui_dropdowns_sync": ui_dropdowns_sync,
        "ui_button_labels": ui_button_labels,
        "ui_button_conditions": ui_button_conditions,
        "ui_dropdown_conditions": ui_dropdown_conditions,
        "ui_layout": ui_layout,
        "ui_balance_dropdown": ui_balance_dropdown,
        "supports_preset_delete": bool(module and getattr(module, "SUPPORTS_PRESET_DELETE", False)),
        "supports_osd_toggle": bool(module and getattr(module, "SUPPORTS_OSD_TOGGLE", False)),
        "supports_osd_trigger": bool(module and getattr(module, "SUPPORTS_OSD_TRIGGER", False)),
        **extra,
    }
    return templates.TemplateResponse("partials/camera_panel.html", ctx)


def _do_reset(session, module, registry: PluginRegistry, sid, ip, port) -> dict:
    """
    Runs the reset sequence via ResetEngine.
    Returns a normalised WebSocket event dict ready to broadcast.
    """
    transport = registry.resolve_transport_for_module(module)
    if transport is None:
        camera_id = getattr(module, "CAMERA_ID", module.__name__)
        raise RuntimeError(f"No transport registered for camera '{camera_id}' — cannot reset.")
    engine = ResetEngine(module, transport, session, sid, ip, port)
    result = engine.run()
    return result.to_ws_event()


def _sync_feature_states(
    session: CameraSession,
    module,
    ip: str,
    port: str,
    registry=None,
    *,
    expected_sid: int,
):
    """Query all feature states from camera and populate session. Runs in executor.

    expected_sid, ip, and port must be captured by the caller before submitting to
    the executor.  Any write is aborted if the session is disconnected, has moved on
    to a different connection (session_id mismatch), or is now targeting a different
    address (covers the session_id-reuse edge case where disconnect → reconnect to a
    new camera bumps session_id back to a value that matches expected_sid).
    """
    sid = expected_sid
    feature_queries = getattr(module, "UI_FEATURE_QUERIES", {})

    import json as _json
    transport = registry.resolve_transport_for_module(module) if registry else None
    response_map = getattr(module, "UI_FEATURE_RESPONSE_MAP", {})
    # BirdDog (JSON REST) declares UI_FEATURE_RESPONSE_MAP/UI_DROPDOWN_RESPONSE_MAP
    # per key; Panasonic (plain "OSL:45:1"-style CGI responses) declares neither —
    # for those keys, parse the plain response directly instead of as JSON.
    is_panasonic = getattr(module, "PROTOCOL", "panasonic") == "panasonic"
    for key, query in feature_queries.items():
        if transport is None:
            continue
        try:
            body = transport.send_command(ip, port, transport.build_query(query))
        except Exception:
            continue
        if not session.connected or session.session_id != sid or session.ip != ip or session.port != port:
            return
        field, value_map = response_map.get(key, (None, {}))
        if field:
            try:
                data = _json.loads(body)
            except Exception:
                continue
            if field in data:
                session.feature_states[key] = value_map.get(data[field], False)
        elif is_panasonic and body:
            session.feature_states[key] = body.rsplit(":", 1)[-1] == "1"

    # Sync plugin dropdown selections
    dropdown_queries = getattr(module, "UI_DROPDOWN_QUERIES", {})
    dropdown_response_map = getattr(module, "UI_DROPDOWN_RESPONSE_MAP", {})
    ui_dropdowns = getattr(module, "UI_DROPDOWNS", {})
    legacy_attrs = {"color_temp": "c_temp_selection", "gamma": "gamma_selection", "linear_matrix": "lmatrix_selection"}
    for key, query in dropdown_queries.items():
        if transport is None:
            continue
        try:
            body = transport.send_command(ip, port, transport.build_query(query))
        except Exception:
            continue
        if not session.connected or session.session_id != sid or session.ip != ip or session.port != port:
            return
        field, value_map = dropdown_response_map.get(key, (None, {}))
        label = None
        if field:
            try:
                data = _json.loads(body)
            except Exception:
                continue
            if field in data:
                label = value_map.get(data[field], "")
        elif is_panasonic and body:
            label = next((opt_label for opt_label, cmd in ui_dropdowns.get(key, []) if cmd == body), None)
        if label is not None:
            session.dropdown_selections[key] = label
            if key in legacy_attrs:
                setattr(session, legacy_attrs[key], label)

    # Sync N-state cycle buttons (UI_BUTTONS[key]["cycle"]) — determine the
    # current index by checking, for each state in turn, whether every one of
    # its commands' addresses currently reads back that command's value.
    ui_buttons = getattr(module, "UI_BUTTONS", {})
    for key, btn_def in ui_buttons.items():
        cycle = btn_def.get("cycle") if isinstance(btn_def, dict) else None
        if not cycle or transport is None:
            continue
        matched_index = None
        for idx, state in enumerate(cycle):
            all_match = True
            for cmd in state.get("cmd", []):
                parsed = _panasonic_query_for_cmd(cmd)
                if parsed is None:
                    all_match = False
                    break
                query, expected = parsed
                try:
                    body = transport.send_command(ip, port, transport.build_query(query))
                except Exception:
                    all_match = False
                    break
                if not session.connected or session.session_id != sid or session.ip != ip or session.port != port:
                    return
                if not body or body.rsplit(":", 1)[-1].strip().upper() != expected.strip().upper():
                    all_match = False
                    break
            if all_match:
                matched_index = idx
                break
        if matched_index is not None:
            session.cycle_states[key] = matched_index


def _panasonic_query_for_cmd(cmd: str) -> "tuple[str, str] | None":
    """Derive (query, expected_value) from a Panasonic control command like "OSL:45:1".

    Panasonic query commands mirror control commands with "O" swapped for "Q"
    on the same address (e.g. control "OSL:45:1" ↔ query "QSL:45"), and the
    response echoes the same "O..."-prefixed string back.
    """
    parts = cmd.split(":")
    if len(parts) != 3 or not parts[0].startswith("O"):
        return None
    prefix, addr, value = parts
    return f"Q{prefix[1:]}:{addr}", value


def _configure_command_maps(session: CameraSession, module):
    """Populate dropdown command maps from UI_DROPDOWNS."""
    ui_dropdowns = getattr(module, "UI_DROPDOWNS", {})
    for key, entries in ui_dropdowns.items():
        cmd_map = {label: cmd for label, cmd in entries if cmd is not None}
        if key == "color_temp":
            session.c_temp_command_map = cmd_map
        elif key == "gamma":
            session.gamma_command_map = cmd_map
        elif key == "linear_matrix":
            session.lmatrix_command_map = cmd_map


# ---------------------------------------------------------------------------
# Routes — Main UI
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    session = _session(request)
    module = _registry(request).resolve_module(session.camera_id)
    ui_buttons = getattr(module, "UI_BUTTONS", {}) if module else _DEFAULT_UI_BUTTONS
    ui_dropdowns = getattr(module, "UI_DROPDOWNS", {}) if module else {}
    ui_dropdowns_sync = set(getattr(module, "UI_BUTTON_DROPDOWN_SYNC", {}).keys()) if module else set()
    ui_button_labels = getattr(module, "UI_BUTTON_LABELS", {}) if module else {}
    ui_button_conditions = getattr(module, "UI_BUTTON_CONDITIONS", {}) if module else {}
    ui_dropdown_conditions = getattr(module, "UI_DROPDOWN_CONDITIONS", {}) if module else {}
    for _gate_keys in ui_dropdown_conditions.values():
        ui_dropdowns_sync.update(_gate_keys)
    ui_layout = getattr(module, "UI_LAYOUT", None) if module else None
    if ui_layout is None:
        ui_layout = _DEFAULT_UI_LAYOUT
    ui_balance_dropdown = getattr(module, "UI_BALANCE_DROPDOWN", None) if module else None
    return templates.TemplateResponse("index.html", {
        "request": request,
        "session": session,
        "ui_buttons": ui_buttons,
        "ui_dropdowns": ui_dropdowns,
        "ui_dropdowns_sync": ui_dropdowns_sync,
        "ui_button_labels": ui_button_labels,
        "ui_button_conditions": ui_button_conditions,
        "ui_dropdown_conditions": ui_dropdown_conditions,
        "ui_balance_dropdown": ui_balance_dropdown,
        "ui_layout": ui_layout,
        "supports_preset_delete": bool(module and getattr(module, "SUPPORTS_PRESET_DELETE", False)),
        "supports_osd_toggle": bool(module and getattr(module, "SUPPORTS_OSD_TOGGLE", False)),
        "supports_osd_trigger": bool(module and getattr(module, "SUPPORTS_OSD_TRIGGER", False)),
    })


# ---------------------------------------------------------------------------
# Routes — Camera scan
# ---------------------------------------------------------------------------

@app.post("/api/camera/scan", response_class=HTMLResponse)
async def scan_cameras(request: Request):
    session = _session(request)
    if session.scan_in_progress:
        return _render_panel(request)
    session.scan_in_progress = True

    loop = asyncio.get_running_loop()
    transports = list(_registry(request).all_transports().items())

    async def _discover_one(name: str, transport):
        def _run():
            try:
                return transport.discover()
            except CameraDiscoveryError as exc:
                logging.error(f"Network scan [{name}] failed: {exc}")
                return []
            except Exception as exc:
                logging.error(f"Network scan [{name}] error: {exc}")
                return []
        return await loop.run_in_executor(_executor, _run)

    logging.info(f"Network scan started ({len(transports)} transport(s))...")
    try:
        results_list = await asyncio.gather(
            *[_discover_one(n, t) for n, t in transports]
        )
        # Merge results, deduplicate by IP
        seen_ips: set[str] = set()
        merged: list[dict] = []
        for results in results_list:
            for cam in results:
                if cam["ip"] not in seen_ips:
                    seen_ips.add(cam["ip"])
                    merged.append(cam)
        session.discovered_cameras = merged
        logging.info(f"Network scan complete: {len(merged)} camera(s) found.")
    except Exception as exc:
        logging.error(f"Network scan error: {exc}")
        session.discovered_cameras = []
    finally:
        session.scan_in_progress = False

    return _render_panel(request)


# ---------------------------------------------------------------------------
# Routes — Connect / Disconnect
# ---------------------------------------------------------------------------

@app.post("/api/camera/connect", response_class=HTMLResponse)
async def connect_camera(request: Request):
    session = _session(request)
    if session.connect_in_progress or session.connected:
        return _render_panel(request)

    form = await request.form()
    ip = (form.get("ip") or "").strip()
    port = (form.get("port") or "80").strip()

    if not ip:
        return _render_panel(request, error="IP address is required.")

    session.connect_in_progress = True
    session.ip = ip
    session.port = port
    logging.info(f"Connecting to camera at {ip}:{port}...")

    loop = asyncio.get_running_loop()
    transports = list(_registry(request).all_transports().items())

    async def _identify_camera():
        """Returns (camera_id, transport_name) for the first transport that responds."""
        async def _try_one(name: str, transport):
            try:
                cid = await loop.run_in_executor(
                    _executor, transport.query_camera_id, ip, port
                )
                return (cid, name) if cid else None
            except Exception as exc:
                logging.debug(f"Transport [{name}] could not identify {ip}:{port}: {exc}")
                return None
        results = await asyncio.gather(*[_try_one(n, t) for n, t in transports])
        return next((r for r in results if r), (None, None))

    try:
        camera_id, found_by = await _identify_camera()
    except Exception as exc:
        logging.error(f"Connect error: {exc}")
        camera_id, found_by = None, None
    finally:
        session.connect_in_progress = False

    if not camera_id:
        logging.error(f"Could not identify camera at {ip}:{port} — no valid response.")
        session.ip = ""
        session.port = "80"
        return _render_panel(request, error=f"No response from {ip}:{port}")

    module = _registry(request).resolve_module(camera_id)
    if module is None:
        if found_by == "birddog":
            logging.warning(
                f"Unknown BirdDog model '{camera_id}' — using generic fallback."
            )
            camera_id = "_BirdDog_Generic"
            module = _registry(request).resolve_module(camera_id)
        else:
            logging.warning(f"Camera identified as '{camera_id}' but no module registered — refusing connect.")
            session.ip = ""
            session.port = "80"
            return _render_panel(request, error=f"Unrecognised camera model: {camera_id}")

    # Correct port to the transport's API port (e.g. BirdDog API is on 8080,
    # not 80 — so if the user typed 80 we fix it here before storing it).
    transport = _registry(request).resolve_transport_for_module(module) if module else None
    if transport is not None and transport.default_port != "80":
        port = transport.default_port
        session.port = port

    session.camera_id = camera_id
    session.connected = True
    session.session_id += 1
    _configure_command_maps(session, module)

    display = getattr(module, "DISPLAY_NAME", camera_id) if module else camera_id
    logging.info(f"Connected: {display} at {ip}:{port} (session {session.session_id})")

    if module:
        _reg = _registry(request)
        _sid = session.session_id
        async def _do_sync():
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(
                _executor,
                lambda: _sync_feature_states(session, module, ip, port, registry=_reg, expected_sid=_sid),
            )
            if session.session_id == _sid:
                await ws_manager.broadcast_json({"type": "feature_sync_done"})
        asyncio.create_task(_do_sync())

    await ws_manager.broadcast_json({"type": "camera_connected", "ip": ip, "camera_id": camera_id})
    return _render_panel(request)


@app.post("/api/camera/disconnect", response_class=HTMLResponse)
async def disconnect_camera(request: Request):
    session = _session(request)
    if session.connected:
        logging.info(f"Disconnected from {session.ip}:{session.port}")
    session.reset_connection()
    await ws_manager.broadcast_json({"type": "camera_disconnected"})
    return _render_panel(request)


# ---------------------------------------------------------------------------
# Routes — Camera state (JSON)
# ---------------------------------------------------------------------------

@app.get("/api/camera/state")
async def camera_state(request: Request):
    session = _session(request)
    return {
        "connected": session.connected,
        "camera_id": session.camera_id,
        "ip": session.ip,
        "port": session.port,
        "reset_in_progress": session.reset_in_progress,
        "preset_delete_in_progress": session.preset_delete_in_progress,
        "balance_in_progress": session.balance_in_progress,
        "feature_states": session.feature_states,
    }


@app.get("/api/camera/panel", response_class=HTMLResponse)
async def camera_panel(request: Request):
    """Return updated camera panel fragment (used by WS refresh trigger)."""
    return _render_panel(request)


# ---------------------------------------------------------------------------
# Routes — Reset
# ---------------------------------------------------------------------------

def _parse_preset_range(form) -> "tuple[int, int] | str":
    """
    Reads the preset-delete range/all fields from the delete-presets form.

    Returns (start, end), or an error message string if the request is malformed.
    """
    if (form.get("preset_delete_all") or "").lower() in ("on", "true", "1"):
        return 0, 99

    try:
        start = int(form.get("preset_start", "0"))
        end = int(form.get("preset_end", "99"))
    except ValueError:
        return "Invalid preset range."
    if not (0 <= start <= end <= 99):
        return "Preset range must be 0–99 with start ≤ end."
    return start, end


@app.post("/api/camera/reset", response_class=HTMLResponse)
async def start_reset(request: Request):
    session = _session(request)
    if not session.connected:
        return _render_panel(request, error="Not connected.")
    if session.reset_in_progress or session.preset_delete_in_progress:
        return _render_panel(request)

    module = _registry(request).resolve_module(session.camera_id)
    if module is None:
        return _render_panel(request, error="Unknown camera type — cannot reset.")

    session.reset_in_progress = True
    registry = request.app.state.registry
    ip, port, sid = session.ip, session.port, session.session_id
    logging.info("Reset sequence started.")

    async def _task():
        loop = asyncio.get_running_loop()
        try:
            event = await loop.run_in_executor(
                _executor,
                lambda: _do_reset(session, module, registry, sid, ip, port),
            )

            # Re-sync UI state from camera so dropdowns/buttons reflect reset values.
            await loop.run_in_executor(
                _executor,
                lambda: _sync_feature_states(session, module, ip, port, registry=registry, expected_sid=sid),
            )
            await ws_manager.broadcast_json(event)
        except Exception as exc:
            logging.exception(f"Reset task error: {exc}")
            session.reset_in_progress = False
            await ws_manager.broadcast_json(
                {"type": "reset_done", "status": "error", "ok": 0, "failed": 0}
            )

    asyncio.create_task(_task())
    return _render_panel(request)


@app.post("/api/camera/delete-presets", response_class=HTMLResponse)
async def start_delete_presets(request: Request):
    session = _session(request)
    if not session.connected:
        return _render_panel(request, error="Not connected.")
    if session.reset_in_progress or session.preset_delete_in_progress:
        return _render_panel(request)

    module = _registry(request).resolve_module(session.camera_id)
    if module is None or not getattr(module, "SUPPORTS_PRESET_DELETE", False):
        return _render_panel(request, error="Preset deletion not supported for this camera.")

    form = await request.form()
    parsed = _parse_preset_range(form)
    if isinstance(parsed, str):
        return _render_panel(request, error=parsed)
    start, end = parsed

    session.preset_delete_in_progress = True
    registry = request.app.state.registry
    ip, port, sid = session.ip, session.port, session.session_id
    logging.info(f"Preset delete started for range {start}-{end}.")

    def _should_abort() -> bool:
        return not (
            session.connected
            and session.session_id == sid
            and session.ip == ip
            and session.port == port
        )

    include_name_thumbnail = bool(getattr(module, "SUPPORTS_PRESET_DELETE_NAME_THUMBNAIL", False))

    async def _task():
        loop = asyncio.get_running_loop()
        try:
            transport = registry.resolve_transport_for_module(module)
            if transport is None:
                logging.error("Preset delete: no transport available.")
                result = {"ok": 0, "failed": 0}
            else:
                result = await loop.run_in_executor(
                    _executor,
                    lambda: delete_presets(
                        transport, ip, port, start, end, _should_abort, include_name_thumbnail
                    ),
                )
            logging.info(
                f"Preset delete finished: {result['ok']} ok, {result['failed']} failed."
            )
            if not _should_abort():
                session.preset_delete_in_progress = False
            await ws_manager.broadcast_json({
                "type": "preset_delete_done",
                "status": "error" if result["failed"] else "ok",
                "ok": result["ok"],
                "failed": result["failed"],
            })
        except Exception as exc:
            logging.exception(f"Preset delete task error: {exc}")
            session.preset_delete_in_progress = False
            await ws_manager.broadcast_json(
                {"type": "preset_delete_done", "status": "error", "ok": 0, "failed": 0}
            )

    asyncio.create_task(_task())
    return _render_panel(request)


# ---------------------------------------------------------------------------
# Routes — Feature toggles
# ---------------------------------------------------------------------------

@app.post("/api/camera/feature/{key}", response_class=HTMLResponse)
async def toggle_feature(request: Request, key: str):
    session = _session(request)
    if not session.connected:
        return _render_panel(request)

    form = await request.form()
    enabled = form.get("enabled", "true").lower() in ("true", "1", "on")
    module = _registry(request).resolve_module(session.camera_id)
    if module is None:
        return _render_panel(request)

    ip, port = session.ip, session.port
    loop = asyncio.get_running_loop()

    ui_buttons = getattr(module, "UI_BUTTONS", {})
    cmd = ui_buttons.get(key, {}).get("on" if enabled else "off")
    transport = _registry(request).resolve_transport_for_module(module)

    def _plugin_toggle():
        if not cmd or transport is None:
            return False
        try:
            transport.send_command(ip, port, transport.build_command(cmd))
            return True
        except Exception as exc:
            logging.error(f"[{key}] transport error: {exc}")
            return False

    ok = await loop.run_in_executor(_executor, _plugin_toggle)

    dropdown_synced = False
    if ok:
        session.feature_states[key] = enabled
        logging.info(f"[{key}] -> {'ON' if enabled else 'OFF'}")
        # Sync any related dropdowns defined in the module
        sync = getattr(module, "UI_BUTTON_DROPDOWN_SYNC", {})
        for dd_key, dd_label in sync.get(key, {}).get(enabled, {}).items():
            session.dropdown_selections[dd_key] = dd_label
            dropdown_synced = True
        # Also re-render the full panel if this button gates another dropdown's
        # enabled/disabled state (see UI_DROPDOWN_CONDITIONS) — its own
        # single-button fragment can't update a different dropdown's disabled attr.
        dropdown_conditions = getattr(module, "UI_DROPDOWN_CONDITIONS", {})
        if any(key in gate_keys for gate_keys in dropdown_conditions.values()):
            dropdown_synced = True
    else:
        logging.error(f"[{key}] -> command failed")

    # If a dropdown was also updated, return the full panel so it re-renders.
    if dropdown_synced:
        return _render_panel(request)

    ui_buttons = getattr(module, "UI_BUTTONS", {})
    return templates.TemplateResponse("partials/feature_btn.html", {
        "request": request,
        "key": key,
        "enabled": session.feature_states.get(key, False),
        "ui_buttons": ui_buttons,
    })


@app.post("/api/camera/cycle/{key}", response_class=HTMLResponse)
async def cycle_feature(request: Request, key: str):
    """Advance an N-state cycle button (UI_BUTTONS[key]["cycle"]) to its next state."""
    session = _session(request)
    if not session.connected:
        return _render_panel(request)

    module = _registry(request).resolve_module(session.camera_id)
    if module is None:
        return _render_panel(request)

    ui_buttons = getattr(module, "UI_BUTTONS", {})
    cycle = ui_buttons.get(key, {}).get("cycle")
    if not cycle:
        logging.warning(f"Cycle '{key}': no cycle states defined.")
        return _render_panel(request)

    target = (session.cycle_states.get(key, 0) + 1) % len(cycle)
    commands = cycle[target].get("cmd", [])
    transport = _registry(request).resolve_transport_for_module(module)
    ip, port = session.ip, session.port
    loop = asyncio.get_running_loop()

    def _plugin_cycle():
        if transport is None:
            return False
        try:
            for cmd in commands:
                transport.send_command(ip, port, transport.build_command(cmd))
            return True
        except Exception as exc:
            logging.error(f"[{key}] cycle transport error: {exc}")
            return False

    ok = await loop.run_in_executor(_executor, _plugin_cycle)
    if ok:
        session.cycle_states[key] = target
        logging.info(f"[{key}] -> {cycle[target].get('label', target)}")
    else:
        logging.error(f"[{key}] -> cycle command failed")

    return _render_panel(request)


# ---------------------------------------------------------------------------
# Routes — Trigger buttons (cmd-only, no toggle state)
# ---------------------------------------------------------------------------

@app.post("/api/camera/trigger/{key}", response_class=HTMLResponse)
async def trigger_action(request: Request, key: str):
    session = _session(request)
    if not session.connected:
        return _render_panel(request)

    module = _registry(request).resolve_module(session.camera_id)
    if module is None:
        return _render_panel(request)

    ui_buttons = getattr(module, "UI_BUTTONS", {})
    cmd = ui_buttons.get(key, {}).get("cmd")
    if not cmd:
        logging.warning(f"Trigger '{key}': no cmd defined.")
        return _render_panel(request)

    ip, port = session.ip, session.port
    loop = asyncio.get_running_loop()

    transport = _registry(request).resolve_transport_for_module(module)

    def _run():
        if transport is None:
            logging.error(f"[{key}] trigger: no transport available.")
            return
        try:
            transport.send_command(ip, port, transport.build_command(cmd))
            logging.info(f"[{key}] trigger sent.")
        except Exception as exc:
            logging.error(f"[{key}] trigger error: {exc}")

    await loop.run_in_executor(_executor, _run)

    return _render_panel(request)


# ---------------------------------------------------------------------------
# Routes — Dropdowns
# ---------------------------------------------------------------------------

@app.post("/api/camera/dropdown/{key}", response_class=HTMLResponse)
async def set_dropdown(request: Request, key: str):
    session = _session(request)
    if not session.connected:
        return _render_panel(request)

    form = await request.form()
    label = (form.get("label") or "").strip()
    module = _registry(request).resolve_module(session.camera_id)
    ip, port = session.ip, session.port
    loop = asyncio.get_running_loop()

    ui_dropdowns = getattr(module, "UI_DROPDOWNS", {})
    options = dict(ui_dropdowns.get(key, []))
    cmd = options.get(label)
    if not cmd:
        logging.warning(f"Dropdown '{key}': no command for label '{label}'")
        return _render_panel(request)
    transport = _registry(request).resolve_transport_for_module(module)

    def _plugin_dropdown():
        if transport is None:
            logging.error(f"Dropdown [{key}]: no transport available.")
            return False
        try:
            transport.send_command(ip, port, transport.build_command(cmd))
            return True
        except Exception as exc:
            logging.error(f"Dropdown [{key}] transport error: {exc}")
            return False

    ok = await loop.run_in_executor(_executor, _plugin_dropdown)
    if ok:
        session.dropdown_selections[key] = label
        _legacy_attrs = {"color_temp": "c_temp_selection", "gamma": "gamma_selection", "linear_matrix": "lmatrix_selection"}
        if key in _legacy_attrs:
            setattr(session, _legacy_attrs[key], label)
        logging.info(f"[{key}] -> {label}")
        # Sync any feature button states that depend on this dropdown
        sync = getattr(module, "UI_BUTTON_DROPDOWN_SYNC", {})
        for btn_key, states in sync.items():
            for btn_state, dd_updates in states.items():
                if key in dd_updates and dd_updates[key] == label:
                    session.feature_states[btn_key] = btn_state
    else:
        logging.error(f"[{key}] -> command failed for '{label}'")
    return _render_panel(request)


# ---------------------------------------------------------------------------
# Routes — Balance
# ---------------------------------------------------------------------------

@app.post("/api/camera/balance/{button_key}", response_class=HTMLResponse)
async def start_balance(request: Request, button_key: str):
    session = _session(request)
    if not session.connected or session.balance_in_progress:
        return _render_panel(request)

    module = _registry(request).resolve_module(session.camera_id)
    if module is None:
        return _render_panel(request)

    if button_key in ("aww_white", "awb_black"):
        aww_required = getattr(module, "AWW_REQUIRED_OPTIONS", [])
        if aww_required and session.c_temp_selection not in aww_required:
            logging.warning(
                f"{'AWW' if button_key == 'aww_white' else 'ABB'} rejected: "
                f"Color Temp must be one of {aww_required}, "
                f"currently '{session.c_temp_selection}'"
            )
            short_options = [opt.removeprefix("White Balance is ") for opt in aww_required]
            return _render_panel(request, error=f"Set Color Temp to an {' or '.join(short_options)} first.")

    ui_buttons = getattr(module, "UI_BUTTONS", {})
    entry = ui_buttons.get(button_key, {})
    command = entry.get("cmd") if isinstance(entry, dict) else None
    if not command:
        logging.warning(f"Balance '{button_key}': no command defined.")
        return _render_panel(request)

    completion_queries = getattr(module, "BALANCE_COMPLETION_QUERIES", {})
    poll_query = completion_queries.get(button_key)
    max_wait = getattr(module, "BALANCE_MAX_WAIT_SECONDS", 10.0)

    transport = _registry(request).resolve_transport_for_module(module)
    if transport is None:
        logging.warning(f"Balance '{button_key}': no transport available.")
        return _render_panel(request)

    session.balance_in_progress = True
    session.balance_token += 1
    token = session.balance_token
    ip, port = session.ip, session.port
    label = "ABB" if button_key == "awb_black" else "AWW"
    logging.info(f"{label} balance started.")

    async def _balance_task():
        loop = asyncio.get_running_loop()
        try:
            await loop.run_in_executor(
                _executor,
                lambda: transport.send_command(ip, port, transport.build_command(command)),
            )

            if not poll_query:
                await asyncio.sleep(2.0)
                session.balance_in_progress = False
                await ws_manager.broadcast_json({"type": "balance_done"})
                return

            deadline = time.time() + max_wait
            prev_val = None
            while time.time() < deadline:
                if session.balance_token != token:
                    return
                await asyncio.sleep(0.25)

                def _probe():
                    try:
                        return transport.send_command(ip, port, transport.build_query(poll_query))
                    except Exception:
                        return None

                val = await loop.run_in_executor(_executor, _probe)
                if val and not val.startswith(("ER1:", "ER2:", "ER3:")):
                    if prev_val is not None and val != prev_val:
                        logging.info(f"{label} balance complete.")
                        break
                    prev_val = val
            else:
                logging.info(f"{label} balance completed successfully.")
        except Exception as exc:
            logging.error(f"Balance task error: {exc}")
        finally:
            if session.balance_token == token:
                session.balance_in_progress = False
            await ws_manager.broadcast_json({"type": "balance_done"})

    asyncio.create_task(_balance_task())
    return _render_panel(request)


# ---------------------------------------------------------------------------
# Routes — File logging
# ---------------------------------------------------------------------------

@app.post("/api/logging")
async def toggle_file_logging(request: Request):
    global _file_handler
    data = await request.json()
    enabled = bool(data.get("enabled", False))
    root = logging.getLogger()
    if enabled:
        if _file_handler is None:
            _file_handler = logging.FileHandler(_LOG_PATH, encoding="utf-8")
            _file_handler.setFormatter(
                logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
            )
            root.addHandler(_file_handler)
            logging.info(f"File logging started → {_LOG_PATH}")
    else:
        if _file_handler is not None:
            logging.info("File logging stopped.")
            root.removeHandler(_file_handler)
            _file_handler.close()
            _file_handler = None
    return JSONResponse({"enabled": enabled, "path": str(_LOG_PATH)})


# ---------------------------------------------------------------------------
# Routes — NDI
# ---------------------------------------------------------------------------

@app.get("/api/ndi/sources")
async def ndi_sources():
    """Return available NDI sources and SDK availability."""
    loop = asyncio.get_running_loop()
    try:
        from ndi.ndi_input import is_available, list_sources
        if not is_available():
            from ndi.ndi_input import _LOAD_ERROR
            return JSONResponse({"sources": [], "ndi_available": False, "error": _LOAD_ERROR})
        sources = await loop.run_in_executor(_executor, list_sources)
        return JSONResponse({"sources": sources, "ndi_available": True})
    except Exception as exc:
        logging.error(f"NDI source discovery failed: {exc}")
        return JSONResponse({"sources": [], "ndi_available": False, "error": str(exc)})


_WAVEFORM_MODES = {"parade", "overlay", "luma"}

@app.websocket("/ws/ndi")
async def ndi_monitor(
    websocket: WebSocket,
    source: str = Query(...),
    mode: str = Query("parade"),
):
    """Stream video + waveform JPEG frames from an NDI source.

    Binary messages are prefixed with a 1-byte type tag:
        0x01 = video JPEG
        0x02 = waveform JPEG

    The client can send a text message ("parade" | "overlay" | "luma") at any
    time to switch the waveform mode without reconnecting.
    """
    await websocket.accept()
    loop = asyncio.get_running_loop()

    from ndi.ndi_input import NDIFrameStream, encode_jpeg
    from ndi.scopes import waveform, vectorscope

    scope_mode = [mode if mode in _WAVEFORM_MODES else "parade"]

    async def _receive_messages():
        """Background task: listen for mode-change messages from the client."""
        try:
            while True:
                text = await websocket.receive_text()
                if text in _WAVEFORM_MODES:
                    scope_mode[0] = text
        except Exception:
            pass

    recv_task = asyncio.create_task(_receive_messages())

    # Dedicated executor for this NDI session — created only while this
    # connection is open, so frame capture/encoding never queues behind
    # camera-control commands on the shared _executor (and vice versa).
    ndi_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="ndi")

    stream = NDIFrameStream(source)
    try:
        await loop.run_in_executor(ndi_executor, stream.open)
    except Exception as exc:
        await websocket.send_text(f"ERROR: {exc}")
        await websocket.close()
        recv_task.cancel()
        ndi_executor.shutdown(wait=False)
        return

    def _process(frame, current_mode):
        video_jpg = encode_jpeg(frame, width=640)
        wave_img  = waveform(frame, mode=current_mode, out_w=640, out_h=360)
        wave_jpg  = encode_jpeg(wave_img, width=640, quality=85)
        vec_img   = vectorscope(frame, out_size=512)
        vec_jpg   = encode_jpeg(vec_img, width=512, quality=85)
        return video_jpg, wave_jpg, vec_jpg

    try:
        while True:
            frame = await loop.run_in_executor(ndi_executor, lambda: stream.next_frame(200))
            if frame is not None:
                current_mode = scope_mode[0]
                video_jpg, wave_jpg, vec_jpg = await loop.run_in_executor(
                    ndi_executor, lambda: _process(frame, current_mode)
                )
                await websocket.send_bytes(b"\x01" + video_jpg)
                await websocket.send_bytes(b"\x02" + wave_jpg)
                await websocket.send_bytes(b"\x03" + vec_jpg)
            else:
                await asyncio.sleep(0.05)
    except (WebSocketDisconnect, Exception):
        pass
    finally:
        recv_task.cancel()
        await loop.run_in_executor(ndi_executor, stream.close)
        ndi_executor.shutdown(wait=False)


# ---------------------------------------------------------------------------
# WebSocket
# ---------------------------------------------------------------------------

@app.websocket("/ws/logs")
async def websocket_logs(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
