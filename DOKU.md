# DOKU — smart-reset-browser

**Last updated:** 2026-04-11

Technical architecture and implementation reference.

---

## Overview

FastAPI server running on `localhost:8765`. The browser is the UI — no desktop GUI framework required. All camera communication is HTTP; real-time UI updates via WebSocket.

```
web_main.py → uvicorn → web/app.py → camera_plugins/ + ndi/
                     ↕ WebSocket
                   browser (HTMX + Vanilla JS)
```

---

## Project Structure

```
smart-reset-browser/
├── web_main.py              # Entry point: uvicorn + system tray + browser open
├── requirements.txt         # Python dependencies
│
├── core/
│   ├── interfaces.py        # CameraProtocol ABC, CameraModule Protocol
│   ├── exceptions.py        # CameraError, PluginError, ...
│   ├── models.py            # DiscoveredCamera, ResetResult, ResetContext
│   ├── registry.py          # PluginRegistry — loads modules and transports
│   └── reset_engine.py      # ResetEngine — dispatches run_reset(context)
│
├── camera_plugins/
│   ├── panasonic/
│   │   ├── transport.py     # HTTP CGI, UDP discovery, model detection
│   │   ├── base.py          # Shared helpers
│   │   └── aw_*.py          # Per-model reset modules
│   └── birddog/
│       ├── transport.py     # REST/JSON, parallel subnet scan, port 8080
│       ├── base.py          # Shared helpers
│       └── p*.py            # Per-model reset modules
│
├── smart_reset/
│   ├── camera_state.py      # CameraSession — singleton session state
│   ├── discovery.py         # Panasonic UDP discovery
│   ├── http_client.py       # send_command(), is_success_response()
│   └── reset_worker.py      # Legacy reset path (Panasonic camera_types fallback)
│
├── ndi/
│   ├── ndi_input.py         # NDI 6 SDK ctypes wrapper
│   └── scopes.py            # Waveform + vectorscope computation (BT.709)
│
├── lib/ndi/                 # Bundled Processing.NDI.Lib.x64.dll
│
└── web/
    ├── app.py               # All FastAPI routes
    ├── ws_manager.py        # WebSocketManager + WebSocketLogHandler
    ├── templates/
    │   ├── base.html        # Layout, all JS, modals
    │   ├── index.html       # Main page content
    │   └── partials/
    │       ├── camera_panel.html   # HTMX fragment — full camera controls
    │       └── feature_btn.html    # HTMX fragment — single toggle button
    └── static/
        └── style.css
```

---

## State

`CameraSession` (`smart_reset/camera_state.py`) is the **only** runtime state container.  
Stored as a singleton in `app.state.session`. Never duplicated elsewhere.

Key fields:
- `ip`, `port`, `connected`, `camera_id`, `session_id`
- `reset_in_progress`, `balance_in_progress`, `connect_in_progress`, `scan_in_progress`
- `feature_states: dict[str, bool]` — toggle button states
- `dropdown_selections: dict[str, str]` — current dropdown selections (plugin modules)
- `discovered_cameras: list[dict]` — results of last network scan

---

## Routes

| Method | Path | Response | Description |
|--------|------|----------|-------------|
| `GET` | `/` | HTML | Main page |
| `GET` | `/api/camera/panel` | HTML fragment | Current camera panel |
| `GET` | `/api/camera/state` | JSON | Session state (debug) |
| `POST` | `/api/camera/scan` | HTML fragment | Start network scan |
| `POST` | `/api/camera/connect` | HTML fragment | Connect (body: `ip`, `port`) |
| `POST` | `/api/camera/disconnect` | HTML fragment | Disconnect |
| `POST` | `/api/camera/reset` | HTML fragment | Start reset sequence |
| `POST` | `/api/camera/feature/{key}` | HTML fragment | Toggle feature (body: `enabled`) |
| `POST` | `/api/camera/trigger/{key}` | HTML fragment | One-shot command |
| `POST` | `/api/camera/dropdown/{key}` | HTML fragment | Set dropdown (body: `label`) |
| `POST` | `/api/camera/balance/{key}` | HTML fragment | Start ABB / AWW |
| `POST` | `/api/logging` | JSON | Enable/disable file logging |
| `GET` | `/api/ndi/sources` | JSON | NDI sources on the network |
| `WS` | `/ws/logs` | WebSocket | Live logs + camera events |
| `WS` | `/ws/ndi?source=NAME&mode=parade` | WebSocket binary | NDI video + scopes |

---

## WebSocket Events (`/ws/logs`)

All messages are JSON.

| Event type | Fields | Trigger |
|------------|--------|---------|
| `log` | `text` | Every log line |
| `reset_done` | `status`, `ok`, `failed` | Reset complete |
| `balance_done` | — | ABB/AWW complete |
| `camera_connected` | `ip`, `camera_id` | Successful connect |
| `camera_disconnected` | — | Disconnect |

Client reacts:
- `reset_done` / `balance_done` → `htmx.trigger('#camera-panel', 'refreshPanel')`
- `camera_connected` → `ndiSyncConnect(ip)` if sync enabled
- `camera_disconnected` → `ndiSyncDisconnect()` if sync enabled

---

## NDI Monitor (`ndi/`)

### `ndi_input.py`

ctypes wrapper around `Processing.NDI.Lib.x64.dll` (NDI 6 SDK).  
Loaded from `lib/ndi/` — no SDK installation required.

Public API:
```python
is_available() -> bool
list_sources(timeout_ms=3000) -> list[str]
grab_frame(ndi_name, timeout_ms=5000) -> np.ndarray   # (H, W, 3) RGB uint8
NDIFrameStream(ndi_name)                               # context manager, continuous
encode_jpeg(frame, width=640, quality=70) -> bytes
```

NDI connection takes ~3–4 seconds for the first frame — normal SDK behaviour.

### `scopes.py`

All computations in **BT.709 / Rec. 709**.

**Waveform** — `waveform(frame, mode, out_w=640, out_h=360) -> np.ndarray (H, W, 3)`

| Mode | Description |
|------|-------------|
| `"parade"` | R, G, B channels side by side (213 px each) |
| `"overlay"` | R, G, B on the same axes |
| `"luma"` | Y = 0.2126·R + 0.7152·G + 0.0722·B, grey trace |

Algorithm: NumPy `bincount` column histogram — single pass, no loops.  
Graticule at 0, 25, 50, 75, 100 IRE.

**Vectorscope** — `vectorscope(frame, out_size=512) -> np.ndarray (H, W, 3)`

BT.709 YCbCr:
```
Cb = (−102·R − 346·G + 450·B) / 1024 + 128
Cr = (+450·R − 408·G −  40·B) / 1024 + 128
```

Graticule: saturation rings every 10 %, crosshair at neutral (128, 128),  
75 % colour-bar target boxes for Y, Cy, G, Mg, R, B.

### `/ws/ndi` binary protocol

Each WebSocket message is prefixed with 1 byte:

| Prefix | Content |
|--------|---------|
| `0x01` | Video JPEG (640×360, quality 70) |
| `0x02` | Waveform JPEG (640×360, quality 85) |
| `0x03` | Vectorscope JPEG (512×512, quality 85) |

Client sends plain text (`"parade"` / `"overlay"` / `"luma"`) to switch waveform mode without reconnecting.

---

## Camera Plugin System

### Plugin fields (per module)

| Field | Type | Description |
|-------|------|-------------|
| `CAMERA_ID` | `str` | Primary model identifier |
| `CAMERA_ID_ALIASES` | `list[str]` | Additional IDs resolved to this module |
| `DISPLAY_NAME` | `str` | Human-readable model name |
| `PROTOCOL` | `str` | `"panasonic"` or `"birddog"` (default: `"panasonic"`) |
| `UI_LAYOUT` | `list[tuple]` | `[(btn1, btn2, btn3, dropdown_key), ...]` per row |
| `UI_BUTTONS` | `dict` | Toggle: `{key: {"on": cmd, "off": cmd}}` / Trigger: `{key: {"cmd": cmd}}` |
| `UI_BUTTON_LABELS` | `dict` | Display names |
| `UI_BUTTON_CONDITIONS` | `dict` | Trigger enable condition: `{key: {"dropdown": k, "value": v}}` |
| `UI_BUTTON_DROPDOWN_SYNC` | `dict` | `{btn: {True: {dd: label}, False: {dd: label}}}` |
| `UI_DROPDOWNS` | `dict` | `{key: [(label, cmd), ...]}` |
| `UI_FEATURE_QUERIES` | `dict` | Poll current feature state on connect |
| `UI_FEATURE_RESPONSE_MAP` | `dict` | Parse poll response |
| `UI_DROPDOWN_QUERIES` | `dict` | Poll current dropdown on connect |
| `UI_DROPDOWN_RESPONSE_MAP` | `dict` | Parse poll response |
| `run_reset(context)` | `function` | Optional custom reset flow |

### Connect flow

1. `POST /api/camera/connect`
2. All transports attempt `query_camera_id(ip, port)` in parallel
3. First response wins — camera module loaded from `PluginRegistry`
4. Port corrected for transport if needed (BirdDog: 8080)
5. `_sync_feature_states()` polls all feature/dropdown states in executor
6. `camera_connected` WS event broadcast

### Reset flow

1. `POST /api/camera/reset`
2. Background task via `ThreadPoolExecutor`
3. `ResetEngine.run()` → `module.run_reset(context)` (plugin path)
4. After reset: `_sync_feature_states()` re-polls camera
5. `reset_done` WS event broadcast

---

## Threading Model

- **Asyncio event loop** — FastAPI routes, WebSocket, state mutations
- **ThreadPoolExecutor** (`_executor`, 4 workers) — all blocking I/O (HTTP, UDP, NDI)
- **Thread → loop callbacks** — `ws_manager.broadcast_from_thread()` via `asyncio.run_coroutine_threadsafe()`
- **Stale worker protection** — `session_id` checked before state mutations in workers

---

## Frontend

- **HTMX** — all button/form interactions; server responds with HTML fragments
- **Jinja2** — server-side rendering; no client-side state
- **WebSocket** — real-time logs and events; reconnects automatically on drop
- **NDI Sync** — `localStorage` key `ndiSyncCamera`; auto-start/stop on `camera_connected` / `camera_disconnected`
- **Themes** — dark/light, `localStorage` key `theme`
- **No build step** — no npm, no bundler

---

## File Logging

`POST /api/logging` — adds or removes a `FileHandler` on the root logger at runtime.  
Log path: `Path.home() / "smart-reset.log"` → typically `C:\Users\username\smart-reset.log`.  
Enabling shows a popup with the exact path and a mailto link to support.

---

## PyInstaller Notes

- `sys.frozen` check in startup — explicit module name lists for `camera_plugins/`
- Templates, static files, and `lib/ndi/` embedded via `--add-data`
- Single-instance enforced via Windows named mutex (`Global\SmartMatchingApp_SingleInstance`)
- System tray via `pystray`; stdout/stderr redirected to `/dev/null` when frozen
