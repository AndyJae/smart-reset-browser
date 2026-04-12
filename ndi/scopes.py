"""
Broadcast scope computations.

waveform(frame, mode, out_w, out_h) -> np.ndarray (H, W, 3) uint8

    mode: "parade"  — R, G, B side by side
          "overlay" — R, G, B drawn on the same axes
          "luma"    — Y (BT.709 luma) single trace

vectorscope(frame, out_size) -> np.ndarray (out_size, out_size, 3) uint8

    YCbCr vectorscope (BT.709 coefficients).
    Cb on X axis, Cr inverted on Y (high Cr / red direction at top).
    Green phosphor trace with crosshair and 75 % colour-bar target marks.
"""

import numpy as np
from PIL import Image, ImageDraw, ImageFont

# Label color for graticule annotations
_LABEL_COLOR = (100, 100, 100)

# Display range: -10 % … 110 % gives 10 % headroom above and below the legal range
_RANGE_MIN = -10.0
_RANGE_MAX =  110.0

_BG = 18

# Graticule lines drawn at every 10 IRE; 0 % and 100 % are slightly brighter
_GRATICULE_LEVELS     = tuple(range(0, 101, 10))           # 0,10,20,...,100
_GRATICULE_COLOR      = np.array([45, 45, 45], dtype=np.uint8)
_GRATICULE_COLOR_KEY  = np.array([70, 70, 70], dtype=np.uint8)  # 0 % and 100 %

_CH_COLORS = np.array([
    [210,  45,  45],   # R
    [ 45, 200,  45],   # G
    [ 45,  90, 220],   # B
], dtype=np.float32)

_LUMA_COLOR = np.array([200, 200, 200], dtype=np.float32)

# 75 % colour-bar target positions (Cb, Cr) in 0-255 range — BT.709
_VECTOR_TARGETS = [
    ("Y",   44, 136, (200, 200,  30)),   # Yellow
    ("Cy", 147,  44, ( 30, 200, 200)),   # Cyan
    ("G",   63,  52, ( 30, 180,  30)),   # Green
    ("Mg", 193, 204, (200,  30, 200)),   # Magenta
    ("R",  109, 212, (210,  45,  45)),   # Red
    ("B",  212, 121, ( 50,  80, 220)),   # Blue
]

_RING_COLOR = np.array([40, 40, 40], dtype=np.uint8)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def waveform(
    frame: np.ndarray,
    mode: str = "parade",
    out_w: int = 640,
    out_h: int = 256,
) -> np.ndarray:
    """Return an (out_h, out_w, 3) uint8 waveform image for *frame*."""
    if mode == "luma":
        return _luma(frame, out_w, out_h)
    if mode == "overlay":
        return _overlay(frame, out_w, out_h)
    return _parade(frame, out_w, out_h)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

try:
    _FONT = ImageFont.load_default(size=9)
except TypeError:
    _FONT = ImageFont.load_default()


def _make_canvas(out_h: int, out_w: int) -> np.ndarray:
    canvas = np.full((out_h, out_w, 3), _BG, dtype=np.uint8)
    img  = Image.fromarray(canvas)
    draw = ImageDraw.Draw(img)
    for level in _GRATICULE_LEVELS:
        y = int((1.0 - (level - _RANGE_MIN) / (_RANGE_MAX - _RANGE_MIN)) * (out_h - 1))
        line_color = tuple(_GRATICULE_COLOR_KEY.tolist()) if level in (0, 100) else tuple(_GRATICULE_COLOR.tolist())
        draw.line([(0, y), (out_w - 1, y)], fill=line_color)
        draw.text((2, y - 9), f"{level}%", fill=_LABEL_COLOR, font=_FONT)
    return np.array(img)


def _col_hist(data: np.ndarray, out_w: int, h: int) -> np.ndarray:
    """Column histograms for a single-channel (h, out_w) uint8 array.

    Returns (out_w, 256) int32 — hist[x, v] = count of pixels in column x
    with value v.
    """
    col_offsets = np.arange(out_w, dtype=np.int32) * 256
    flat = (data.astype(np.int32) + col_offsets).ravel()
    return np.bincount(flat, minlength=out_w * 256).reshape(out_w, 256).astype(np.int32)


def _draw_hist(
    canvas: np.ndarray,
    hist: np.ndarray,
    color: np.ndarray,
    h: int,
    out_h: int,
    x_off: int = 0,
) -> None:
    cap = max(1.0, h * 0.04)
    brightness = np.clip(hist.astype(np.float32) / cap, 0.0, 1.0)
    xs, vs = np.nonzero(brightness > 0)
    if xs.size == 0:
        return
    pct = vs.astype(np.float32) * (100.0 / 255.0)
    ys = ((1.0 - (pct - _RANGE_MIN) / (_RANGE_MAX - _RANGE_MIN)) * (out_h - 1)).clip(0, out_h - 1).astype(np.int32)
    bright = brightness[xs, vs]
    pixels = (bright[:, np.newaxis] * color).clip(0, 255).astype(np.uint8)
    canvas[ys, x_off + xs] = np.maximum(canvas[ys, x_off + xs], pixels)


# ---------------------------------------------------------------------------
# Mode implementations
# ---------------------------------------------------------------------------

def _parade(frame: np.ndarray, out_w: int, out_h: int) -> np.ndarray:
    h, sw = frame.shape[0], out_w // 3
    small = np.array(
        Image.fromarray(frame).resize((sw, h), Image.BILINEAR), dtype=np.uint8
    )
    canvas = _make_canvas(out_h, out_w)
    for c, color in enumerate(_CH_COLORS):
        _draw_hist(canvas, _col_hist(small[:, :, c], sw, h), color, h, out_h, x_off=c * sw)
    canvas[:, sw - 1]     = _GRATICULE_COLOR
    canvas[:, sw * 2 - 1] = _GRATICULE_COLOR
    return canvas


def _overlay(frame: np.ndarray, out_w: int, out_h: int) -> np.ndarray:
    h = frame.shape[0]
    small = np.array(
        Image.fromarray(frame).resize((out_w, h), Image.BILINEAR), dtype=np.uint8
    )
    canvas = _make_canvas(out_h, out_w)
    for c, color in enumerate(_CH_COLORS):
        _draw_hist(canvas, _col_hist(small[:, :, c], out_w, h), color, h, out_h)
    return canvas


def _luma(frame: np.ndarray, out_w: int, out_h: int) -> np.ndarray:
    h = frame.shape[0]
    Y = (
        0.2126 * frame[:, :, 0].astype(np.float32)
        + 0.7152 * frame[:, :, 1].astype(np.float32)
        + 0.0722 * frame[:, :, 2].astype(np.float32)
    ).clip(0, 255).astype(np.uint8)
    small = np.array(
        Image.fromarray(Y).resize((out_w, h), Image.BILINEAR), dtype=np.uint8
    )
    canvas = _make_canvas(out_h, out_w)
    _draw_hist(canvas, _col_hist(small, out_w, h), _LUMA_COLOR, h, out_h)
    return canvas


# ---------------------------------------------------------------------------
# Vectorscope
# ---------------------------------------------------------------------------

def vectorscope(frame: np.ndarray, out_size: int = 256) -> np.ndarray:
    """Return a (out_size, out_size, 3) uint8 vectorscope image."""
    fr = frame[:, :, 0].astype(np.float32)
    fg = frame[:, :, 1].astype(np.float32)
    fb = frame[:, :, 2].astype(np.float32)

    cb = ((-102.0 * fr - 346.0 * fg + 450.0 * fb) / 1024.0 + 128.0).clip(0, 255).astype(np.int32)
    cr = (( 450.0 * fr - 408.0 * fg -  40.0 * fb) / 1024.0 + 128.0).clip(0, 255).astype(np.int32)

    # 256×256 accumulator — row = Cr, column = Cb
    acc = np.bincount((cr * 256 + cb).ravel(), minlength=256 * 256).reshape(256, 256).astype(np.float32)

    # Normalise: cap at 0.1 % of total pixels so sparse signals still show up
    cap = max(1.0, frame.shape[0] * frame.shape[1] * 0.001)
    trace = np.clip(acc / cap, 0.0, 1.0)
    trace = (trace[::-1] * 210).astype(np.uint8)   # flip: high Cr (red) at top

    # --- Graticule on black canvas ---
    canvas = np.zeros((256, 256, 3), dtype=np.uint8)

    # Saturation rings every 10 % — 100 % = radius 128 px
    ys, xs = np.ogrid[:256, :256]
    dist = np.sqrt((xs - 128.0) ** 2 + (ys - 128.0) ** 2)
    for pct in range(10, 101, 10):
        mask = np.abs(dist - 128.0 * pct / 100.0) < 0.7
        canvas[mask] = _RING_COLOR

    # Crosshair through neutral (Cb=128, Cr=128)
    canvas[128, :] = _RING_COLOR
    canvas[:, 128] = _RING_COLOR

    # --- Overlay the signal trace (green channel only; overrides graticule) ---
    trace_on = trace > 5
    canvas[trace_on, 0] = 0
    canvas[trace_on, 1] = trace[trace_on]
    canvas[trace_on, 2] = 0

    # --- 75 % target boxes + labels (PIL) ---
    img  = Image.fromarray(canvas)
    draw = ImageDraw.Draw(img)
    for name, tcb, tcr, color in _VECTOR_TARGETS:
        cy = 255 - tcr   # invert: high Cr at top
        draw.rectangle([tcb - 3, cy - 3, tcb + 3, cy + 3], outline=color)
        # Label offset away from centre
        dx, dy = tcb - 128, cy - 128
        length = max(1.0, (dx ** 2 + dy ** 2) ** 0.5)
        lx = int(tcb + dx / length * 13)
        ly = int(cy  + dy / length * 13) - 4
        draw.text((lx, ly), name, fill=color, font=_FONT)
    canvas = np.array(img)

    if out_size != 256:
        canvas = np.array(Image.fromarray(canvas).resize((out_size, out_size), Image.NEAREST))

    return canvas
