# smart-reset-browser

Browser-based camera reset, control, and NDI monitoring tool for PTZ cameras.  
Runs fully local — the browser is the UI, no cloud deployment required.

---

## What it does

- Connects to PTZ cameras (Panasonic, BirdDog) over the local network
- Detects the camera model automatically and runs a full reset sequence
- Provides direct control of advanced camera features (Gamma, Matrix, Auto Iris, etc.)
- Streams a live NDI feed with waveform monitor and vectorscope directly in the browser

---

## Requirements

- Python **3.10 or newer**
- Windows (NDI monitor is Windows-only; reset/control works cross-platform)
- Network access to the camera (same LAN)
- NDI output enabled on the camera for the NDI monitor

The NDI runtime (`Processing.NDI.Lib.x64.dll`) is included in `lib/ndi/` — no SDK installation required.

---

## Installation

```bash
git clone https://github.com/AndyJae/smart-reset-browser.git
cd smart-reset-browser
python -m venv .venv
.venv\Scripts\activate      # Windows
pip install -r requirements.txt
```

---

## Start

```bash
python web_main.py
```

The browser opens automatically at `http://localhost:8765`.

> On Windows, use `py web_main.py` if `python` is not found.

---

## Usage

| Feature | Description |
|---------|-------------|
| **Scan Network** | Discovers cameras on the LAN (Panasonic: UDP broadcast, BirdDog: HTTP scan) |
| **Connect** | Connects to the camera — model is detected automatically |
| **Reset Camera** | Runs the full reset sequence; UI state re-syncs from the camera afterwards |
| **ABB (Black)** | Automatic black balance (Panasonic) |
| **AWW (White)** | Automatic white balance — color temp must be set first (Panasonic) |
| **Feature Buttons** | Toggle camera features (Auto Focus, Auto Iris, Gamma, Matrix, etc.) on/off |
| **Dropdowns** | Select camera modes (Exposure, White Balance, Color Temp, etc.) |
| **Trigger Buttons** | One-shot commands — enabled only when the related mode is active |
| **Open Camera** | Opens the camera's web GUI in the browser |
| **File Logging** | Writes all operation logs to `~/smart-reset.log` for debugging |
| **NDI Monitor** | Live NDI feed + waveform (RGB Parade / Overlay / Luma Y) + vectorscope (YCbCr BT.709) |

---

## NDI Monitor

1. Enable NDI output on the camera
2. Check **Sync with camera** to start/stop the feed automatically with the camera connection  
   — or click **Refresh** then **Start** manually
3. Choose waveform mode: **RGB Parade**, **RGB Overlay**, or **Luma (Y)**
4. Click any image to open fullscreen

> The first frame takes **3–4 seconds** — normal NDI connection negotiation.

### Waveform — Rec. 709

All modes computed in BT.709 colour space. Graticule at 0, 25, 50, 75, 100 IRE.

| Mode | Description |
|------|-------------|
| RGB Parade | R, G, B channels side by side |
| RGB Overlay | R, G, B on the same axes |
| Luma (Y) | Y = 0.2126·R + 0.7152·G + 0.0722·B |

### Vectorscope — Rec. 709

YCbCr BT.709 trace with saturation rings every 10 %, crosshair at neutral, and 75 % colour-bar target boxes (Y, Cy, G, Mg, R, B).

---

## Supported Cameras

### Panasonic
AW-UE30 / UE40 / UE50 / UE70 / UE80 / UE100 / UE145 / UE150A / UE160  
AW-HE40 / HE42 / HE50 / HE60 / HE120 / HE130 / HR140  
AK-UB300

### BirdDog
- P200 / A200 / A300 — full colour matrix (14 params)
- P100 / PF120 — colour matrix (12 params)
- P110 / P120 — colour matrix (12 params)
- P4k / P400 / P240 — no colour matrix
- Any other BirdDog model — generic fallback

---

## Project Structure

```
smart-reset-browser/
├── web_main.py              # Entry point: server + tray icon + browser
├── requirements.txt
│
├── core/                    # Manufacturer-agnostic interfaces and engine
├── camera_plugins/          # Manufacturer plugins
│   ├── panasonic/
│   └── birddog/
├── smart_reset/             # Session state, discovery, HTTP client
│
├── ndi/                     # NDI monitor: frame capture + scope computation
│   ├── ndi_input.py         # NDI 6 SDK ctypes wrapper
│   └── scopes.py            # Waveform + vectorscope (BT.709)
│
├── lib/ndi/                 # Bundled NDI runtime DLL (Windows)
│
└── web/
    ├── app.py               # FastAPI — all routes
    ├── ws_manager.py        # WebSocket manager
    ├── templates/           # Jinja2 templates
    └── static/              # CSS
```

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

---

## Technology

- **Backend:** FastAPI + uvicorn
- **Frontend:** HTMX + Jinja2 + Vanilla JS
- **NDI input:** ctypes against NDI 6 SDK (`Processing.NDI.Lib.x64.dll`)
- **Scopes:** NumPy column-histogram waveform + YCbCr vectorscope; Pillow for JPEG encode
- **Real-time:** WebSocket for logs, camera events, and NDI binary stream

---

## License

© medien-support.com — All rights reserved.
