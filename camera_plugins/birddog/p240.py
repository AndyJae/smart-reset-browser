"""
camera_plugins/birddog/p240.py — BirdDog P240 reset module.

Reset sections:
  POST /birddogexpsetup     — Exposure
  POST /birddogwbsetup      — White Balance
  POST /birddogpicsetup     — Picture
  POST /birddogadvancesetup — Advanced

NOTE: /birddogcmsetup is N/A on P240 — colour matrix is not supported.
"""

from __future__ import annotations

from camera_plugins.birddog.base import PROTOCOL, query_raw, send_post  # noqa: F401

CAMERA_ID = "P240"
CAMERA_ID_ALIASES = ["P240", "BirdDog P240"]
DISPLAY_NAME = "BirdDog P240"
# PROTOCOL imported from base ("birddog")

RESET_COMMANDS: list = []

# ---------------------------------------------------------------------------
# UI definitions
# ---------------------------------------------------------------------------

UI_LAYOUT = [
    ('auto_iris', 'auto_focus', None, 'exp_mode'),
    (None,        None,         'wb_trigger', 'wb_mode'),
]

UI_BUTTONS: dict = {
    "auto_focus": {
        "on":  'POST /birddogptz {"FocusMode": "Auto"}',
        "off": 'POST /birddogptz {"FocusMode": "Manual"}',
    },
    "auto_iris": {
        "on":  'POST /birddogexpsetup {"ExpMode": "FULL-AUTO"}',
        "off": 'POST /birddogexpsetup {"ExpMode": "MANUAL"}',
    },
    "wb_trigger": {
        "cmd": 'POST /birddogwbsetup {"OnePushTrigger": "Trigger"}',
    },
}

UI_BUTTON_CONDITIONS: dict = {
    "wb_trigger": {"dropdown": "wb_mode", "value": "One Push"},
}

UI_FEATURE_QUERIES: dict = {
    "auto_focus": "GET /birddogptz",
    "auto_iris":  "GET /birddogexpsetup",
}

UI_FEATURE_RESPONSE_MAP: dict = {
    "auto_focus": ("FocusMode", {"Auto": True, "Manual": False}),
    "auto_iris":  ("ExpMode",   {"FULL-AUTO": True}),
}

UI_BUTTON_LABELS: dict = {
    "auto_focus": "Auto Focus",
    "auto_iris":  "Auto Iris",
    "wb_trigger": "White Balance",
    "exp_mode":   "Exposure Mode",
    "wb_mode":    "White Balance",
}

UI_BUTTON_DROPDOWN_SYNC: dict = {
    "auto_iris": {
        True:  {"exp_mode": "Full Auto"},
        False: {"exp_mode": "Manual"},
    },
}

UI_DROPDOWNS: dict = {
    "exp_mode": [
        ("Full Auto",    'POST /birddogexpsetup {"ExpMode": "FULL-AUTO"}'),
        ("Iris Pri",     'POST /birddogexpsetup {"ExpMode": "IRIS-PRI"}'),
        ("Shutter Pri",  'POST /birddogexpsetup {"ExpMode": "SHUTTER-PRI"}'),
        ("Manual",       'POST /birddogexpsetup {"ExpMode": "MANUAL"}'),
    ],
    "wb_mode": [
        ("Auto",         'POST /birddogwbsetup {"WbMode": "AUTO"}'),
        ("Indoor",       'POST /birddogwbsetup {"WbMode": "INDOOR"}'),
        ("Outdoor",      'POST /birddogwbsetup {"WbMode": "OUTDOOR"}'),
        ("Outdoor Auto", 'POST /birddogwbsetup {"WbMode": "OUTDOOR-AUTO"}'),
        ("One Push",     'POST /birddogwbsetup {"WbMode": "ONEPUSH"}'),
        ("ATW",          'POST /birddogwbsetup {"WbMode": "ATW"}'),
        ("Manual",       'POST /birddogwbsetup {"WbMode": "MANUAL"}'),
    ],
}

UI_DROPDOWN_QUERIES: dict = {
    "exp_mode": "GET /birddogexpsetup",
    "wb_mode":  "GET /birddogwbsetup",
}

UI_DROPDOWN_RESPONSE_MAP: dict = {
    "exp_mode": ("ExpMode", {
        "FULL-AUTO":   "Full Auto",
        "IRIS-PRI":    "Iris Pri",
        "SHUTTER-PRI": "Shutter Pri",
        "MANUAL":      "Manual",
    }),
    "wb_mode": ("WbMode", {
        "AUTO":         "Auto",
        "INDOOR":       "Indoor",
        "OUTDOOR":      "Outdoor",
        "OUTDOOR-AUTO": "Outdoor Auto",
        "ONEPUSH":      "One Push",
        "ATW":          "ATW",
        "MANUAL":       "Manual",
    }),
}

# ---------------------------------------------------------------------------
# Reset defaults
# ---------------------------------------------------------------------------

_EXP_DEFAULTS = {
    "ExpMode":          "FULL-AUTO",
    "ExpCompEn":        "Off",
    "ExpCompLvl":       "0",
    "ShutterSpeed":     "8",
    "IrisLevel":        "16",
    "GainLevel":        "2",
    "BrightLevel":      "19",
    "AeResponse":       "1",
    "SlowShutterEn":    "Off",
    "SlowShutterLimit": "0",
    "GainLimit":        "9",
    "HighSensitivity":  "Off",
}

_WB_DEFAULTS = {
    "WbMode":   "AUTO",
    "Select":   "STD",
    "Speed":    "3",
    "Offset":   "7",
    "Phase":    "7",
    "Level":    "7",
    "Matrix":   "Off",
    "BlueGain": "128",
    "RedGain":  "128",
    "BG":       "0",
    "BR":       "0",
    "GB":       "0",
    "GR":       "0",
    "RB":       "0",
    "RG":       "0",
    "ColorTemp":"5700",
}

_PIC_DEFAULTS = {
    "BackLightCom":      "Off",
    "ChromeSuppress":    "OFF",
    "Color":             "8",
    "Contrast":          "1",
    "Effect":            "Off",
    "Flip":              "Off",
    "Gamma":             "0",
    "HighlightComp":     "OFF",
    "HighlightCompMask": "0",
    "Hue":               "7",
    "IRCutFilter":       "Off",
    "Mirror":            "Off",
    "NoiseReduction":    "3",
    "Sharpness":         "0",
    "Stabilizer":        "Off",
    "TWODNR":            "2",
    "ThreeDNR":          "2",
    "WideDynamicRange":  "Off",
    "LowLatency":        "Off",
    "NDFilter":          "2",
}

_ADV_DEFAULTS = {
    "GammaOffset":      "0",
    "HighResolution":   "Off",
    "Brightness":       "2",
    "BrightnessComp":   "STANDARD",
    "CompLevel":        "LOW",
    "VideoEnhancement": "Off",
}

# ---------------------------------------------------------------------------
# Reset entry point
# ---------------------------------------------------------------------------

def run_reset(context) -> None:
    """Resets all image settings to defaults. Colour matrix is N/A on P240."""
    import json

    pic_defaults = dict(_PIC_DEFAULTS)
    raw = query_raw(context, "/birddogpicsetup")
    if raw:
        try:
            current = json.loads(raw)
            pic_defaults["LowLatency"] = current.get("LowLatency", "Off")
        except (json.JSONDecodeError, TypeError):
            pass

    sections = [
        ("Exposure",    "/birddogexpsetup",     _EXP_DEFAULTS),
        ("WhiteBalance","/birddogwbsetup",       _WB_DEFAULTS),
        ("Picture",     "/birddogpicsetup",      pic_defaults),
        ("Advanced",    "/birddogadvancesetup",  _ADV_DEFAULTS),
        # ColourMatrix (/birddogcmsetup) is N/A on P240 — skipped.
    ]
    for label, path, defaults in sections:
        context.logging.info(f"BirdDog P240: resetting {label}...")
        ok = send_post(context, label, path, defaults)
        if ok:
            context.logging.info(f"BirdDog P240: {label} OK.")
        else:
            context.logging.warning(f"BirdDog P240: {label} failed — no response.")
