"""
camera_plugins/panasonic/aw_he50.py — Panasonic AW-HE50 series

Older-generation compact HD PTZ camera (circa 2011).
Simpler feature set than HE120/HE130: no filmlike gamma, no adaptive matrix,
no colour correction zones, no knee aperture, no skin tone detail.
Commands from Panasonic HD/4K Integrated Camera Interface Specifications v1.12 (2020).
Helper functions come from camera_plugins/panasonic/base.py.
"""

from camera_plugins.panasonic.base import (
    PROTOCOL,
    apply_reset_commands as _apply_reset_commands,
    build_entries as _build_entries,
    ensure_dropdown_value as _ensure_dropdown_value,
    filter_entries as _filter_entries,
    send_set_command as _send_set_command,
    skip_reset_commands as _skip_reset_commands,
)

CAMERA_ID         = "AW-HE50"
CAMERA_ID_ALIASES = ["AW-HE50H", "AW-HE50E", "AW-HE50S"]
DISPLAY_NAME      = "Panasonic AW-HE50"

# ---------------------------------------------------------------------------
# RESET_COMMANDS
# ---------------------------------------------------------------------------

RESET_COMMANDS = [
    # White balance ATW targets
    ("ATW TARGET R",  "OSJ", "0D", "80"),
    ("ATW TARGET B",  "OSJ", "0E", "80"),
    ("ATW SPEED",     "OSI", "25", "0"),
    # Gamma (HD/Normal only)
    ("GAMMA",         "OSA", "6A", "76"),
    # DRS
    ("DRS",           "OSE", "33", "0"),
    # Chroma
    ("CHROMA LEVEL",  "OSD", "B0", "80"),
    ("CHROMA PHASE",  "OSJ", "0B", "80"),
    # Knee — set to OFF only
    ("KNEE MODE",     "OSA", "2D", "0"),
    # White clip — set level then disable
    ("WHITE CLIP",    "OSA", "2E", "1"),
    ("WHITE CLIP LEVEL", "OSA", "2A", "13"),
    ("WHITE CLIP",    "OSA", "2E", "0"),
    # Detail
    ("DNR",           "OSD", "3A", "00"),
    ("MASTER DETAIL", "OSA", "30", "80"),
    ("DETAIL CORING", "OSJ", "12", "0F"),
    ("V DETAIL LEVEL","OSD", "A1", "80"),
    # Pedestal / picture level
    ("MASTER PEDESTAL","OSJ", "0F", "800"),
    ("PICTURE LEVEL", "OSD", "48", "32"),
    ("AWB GAIN OFFSET","OSJ", "0C", "0"),
]

# ---------------------------------------------------------------------------
# UI definition
# ---------------------------------------------------------------------------

UI_BUTTONS = {
    "auto_focus": {"on": "OAF:1",    "off": "OAF:0"},
    "auto_iris":  {"on": "ORS:1",    "off": "ORS:0"},
    "awb_black":  {"cmd": "OAS"},
    "aww_white":  {"cmd": "OWS"},
    "drs":        {"on": "OSE:33:1", "off": "OSE:33:0"},
    "white_clip": {"on": "OSA:2E:1", "off": "OSA:2E:0"},
}

UI_BUTTON_LABELS = {
    "auto_focus": "Auto Focus",
    "auto_iris":  "Auto Iris",
    "drs":        "DRS",
    "white_clip": "White Clip",
    "awb_black":  "ABB (Black)",
    "aww_white":  "AWW (White)",
}

UI_LAYOUT = [
    ("drs",        "auto_iris",  "auto_focus", "color_temp"),
    ("white_clip", "awb_black",  "aww_white",  None),
]

UI_DROPDOWNS = {
    "color_temp": [
        ("White Balance is AWB A",        "OAW:1"),
        ("White Balance is AWB B",        "OAW:2"),
        ("White Balance is Preset 3200K", "OAW:4"),
        ("White Balance is Preset 5600K", "OAW:5"),
        ("White Balance is VAR",          "OAW:9"),
        ("White Balance is ATW",          "OAW:0"),
    ],
}

AWW_REQUIRED_OPTIONS = ["White Balance is AWB A", "White Balance is AWB B"]

BALANCE_COMPLETION_QUERIES = {
    "awb_black": "QAW",
    "aww_white": "QAW",
}

UI_FEATURE_QUERIES = {
    "auto_focus": "QAF",
    "auto_iris":  "QRS",
    "drs":        "QSE:33",
    "white_clip": "QSA:2E",
}

UI_DROPDOWN_QUERIES = {
    "color_temp": "QAW",
}

POST_RESET_FEATURE_STATES = [
    ("auto_iris",  True),
    ("auto_focus", False),
    ("drs",        False),
    ("white_clip", False),
]

POST_RESET_DROPDOWN_DEFAULTS = {
    "color_temp": "White Balance is ATW",
}

POST_RESET_STATUS_QUERIES = [
    ("Auto Iris",  "QRS"),
    ("Auto Focus", "QAF"),
    ("DRS",        "QSE:33"),
    ("White Clip", "QSA:2E"),
    ("White Balance Mode", "QAW"),
]

# ---------------------------------------------------------------------------
# Command key sets
# ---------------------------------------------------------------------------

_ATW_KEYS = {("OSJ", "0D"), ("OSJ", "0E")}

# ---------------------------------------------------------------------------
# Reset logic
# ---------------------------------------------------------------------------

def _prepare_reset_environment(context) -> dict:
    prep = {"gain_default": False}

    context.logging.info("Reset prep: setting GAIN to 0dB")
    prep["gain_default"] = _ensure_dropdown_value(
        context, "GAIN", "QGU", "OGU", "08"
    )

    return prep


def _run_reset_sequence(context, _prep: dict) -> None:
    entries = _build_entries(RESET_COMMANDS)

    atw = _filter_entries(entries, _ATW_KEYS)

    handled: set[int] = set()

    def _mark(*groups):
        for g in groups:
            for e in g:
                handled.add(e["index"])

    if atw:
        _ensure_dropdown_value(context, "WHITE BALANCE MODE", "QAW", "OAW", "0")  # ATW
        _apply_reset_commands(context, atw)
        _mark(atw)

    remaining = [e for e in entries if e["index"] not in handled]
    _apply_reset_commands(context, remaining)


def run_reset(context) -> None:
    prep = _prepare_reset_environment(context)
    _run_reset_sequence(context, prep)
