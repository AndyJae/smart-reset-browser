# AGENTS.md — smart-reset-browser

## Purpose

Browser-based PTZ camera reset, control, and NDI monitoring tool.

- Local FastAPI server on `localhost:8765`
- Browser UI via HTMX + Jinja2 — no frontend framework, no build step
- Camera communication: HTTP (Panasonic CGI / BirdDog REST)
- Camera modules loaded via plugin registry from `camera_plugins/`
- NDI monitor: live video + waveform + vectorscope streamed via WebSocket
- Can be bundled with PyInstaller into a single Windows executable

**Scope of this repo:** Reset, control, and NDI display only.

---

## Architecture

```
web_main.py → uvicorn → web/app.py → camera_plugins/ + ndi/
                      ↕ WebSocket
                    browser (HTMX + Vanilla JS)
```

### Key directories

| Path | Role |
|------|------|
| `core/` | Interfaces, registry, reset engine |
| `camera_plugins/panasonic/` | Panasonic CGI plugin modules |
| `camera_plugins/birddog/` | BirdDog REST plugin modules |
| `smart_reset/` | Session state, discovery, HTTP client |
| `ndi/` | NDI 6 SDK ctypes wrapper + BT.709 scope computation |
| `lib/ndi/` | Bundled `Processing.NDI.Lib.x64.dll` |
| `web/app.py` | All FastAPI routes |
| `web/templates/` | Jinja2 HTML |
| `web/static/` | CSS |

---

## Plugin module fields

| Field | Description |
|-------|-------------|
| `CAMERA_ID` | Primary model string |
| `CAMERA_ID_ALIASES` | Additional model strings mapped to this module |
| `DISPLAY_NAME` | Human-readable name |
| `PROTOCOL` | `"panasonic"` or `"birddog"` (default: `"panasonic"`) |
| `UI_LAYOUT` | `[(btn1, btn2, btn3, dropdown_key), ...]` |
| `UI_BUTTONS` | Toggle: `{"on": cmd, "off": cmd}` / Trigger: `{"cmd": cmd}` |
| `UI_BUTTON_LABELS` | Display names |
| `UI_BUTTON_CONDITIONS` | Trigger enable condition |
| `UI_BUTTON_DROPDOWN_SYNC` | Button ↔ dropdown sync rules |
| `UI_DROPDOWNS` | `{key: [(label, cmd), ...]}` |
| `UI_FEATURE_QUERIES` | Poll feature state on connect |
| `UI_FEATURE_RESPONSE_MAP` | Parse poll response |
| `UI_DROPDOWN_QUERIES` | Poll dropdown state on connect |
| `UI_DROPDOWN_RESPONSE_MAP` | Parse poll response |
| `run_reset(context)` | Optional custom reset flow |

---

## API endpoints

| Method | Path | Response | Description |
|--------|------|----------|-------------|
| `GET` | `/` | HTML | Main page |
| `GET` | `/api/camera/panel` | HTML fragment | Camera panel |
| `GET` | `/api/camera/state` | JSON | Session state |
| `POST` | `/api/camera/scan` | HTML fragment | Network scan |
| `POST` | `/api/camera/connect` | HTML fragment | Connect |
| `POST` | `/api/camera/disconnect` | HTML fragment | Disconnect |
| `POST` | `/api/camera/reset` | HTML fragment | Reset sequence |
| `POST` | `/api/camera/feature/{key}` | HTML fragment | Toggle feature |
| `POST` | `/api/camera/trigger/{key}` | HTML fragment | Trigger command |
| `POST` | `/api/camera/dropdown/{key}` | HTML fragment | Set dropdown |
| `POST` | `/api/camera/balance/{key}` | HTML fragment | ABB / AWW |
| `POST` | `/api/logging` | JSON | File logging on/off |
| `GET` | `/api/ndi/sources` | JSON | NDI sources |
| `WS` | `/ws/logs` | WebSocket | Logs + events |
| `WS` | `/ws/ndi` | WebSocket binary | NDI stream |

## WebSocket events

| Type | Fields | Trigger |
|------|--------|---------|
| `log` | `text` | Every log line |
| `reset_done` | `status`, `ok`, `failed` | Reset complete |
| `balance_done` | — | Balance complete |
| `camera_connected` | `ip`, `camera_id` | Connect success |
| `camera_disconnected` | — | Disconnect |

---

## Hard rules

1. Only change what belongs to the task.
2. No refactoring without explicit instruction.
3. Blocking operations never directly in the asyncio event loop — always `run_in_executor`.
4. State only in `CameraSession` — no other global state.
5. HTMX responses are HTML fragments, not JSON (except `/api/camera/state`).
6. NDI input via ctypes against NDI 6 SDK only — no `opencv-python`, no `ndi-python`, no FFmpeg.
7. Do not invent camera API commands or response formats.
8. No new dependencies without clear need.
9. `camera_panel.html` renders as a complete fragment with `id="camera-panel"` — no double wrapper.
10. No `setTimeout` or client polling — real-time via WebSocket only.

---

## Change priorities

1. Correctness
2. Stability (asyncio loop free)
3. Backward compatibility with existing camera modules
4. Minimal change
5. Readability
