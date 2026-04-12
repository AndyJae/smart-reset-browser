"""
camera_plugins/panasonic/aw_ue150.py — Panasonic AW-UE150A

Migrated from camera_types/camera_aw_ue150.py.
RESET_COMMANDS are derived from AW-UE160 via a model-specific transform.
Helper functions come from camera_plugins/panasonic/base.py.
context.send_command() returns str | None (new ResetContext API).
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
from camera_plugins.panasonic.aw_ue160 import RESET_COMMANDS as _UE160_RESET_COMMANDS

CAMERA_ID        = "AW-UE150A"
CAMERA_ID_ALIASES = ["AW-UE150"]
DISPLAY_NAME     = "Panasonic AW-UE150A"

# ---------------------------------------------------------------------------
# RESET_COMMANDS — derived from UE160 with UE150A-specific transforms
# ---------------------------------------------------------------------------

_MATRIX_USER_VALUES = {
    "MATRIX(R-G)_N": ("OSD", "A4", "80"),
    "MATRIX(R-B)_N": ("OSD", "A5", "80"),
    "MATRIX(G-R)_N": ("OSD", "A6", "80"),
    "MATRIX(G-B)_N": ("OSD", "A7", "80"),
    "MATRIX(B-R)_N": ("OSD", "A8", "80"),
    "MATRIX(B-G)_N": ("OSD", "A9", "80"),
}

_SKIP_LABEL_PREFIXES = (
    "MASTER FLARE",
    "R FLARE",
    "G FLARE",
    "B FLARE",
    "WHITE SHADING",
)

_REMOVE_RESET_LABELS = {
    "R PEDESTAL",
    "G PEDESTAL",
    "B PEDESTAL",
    "R GAIN ACH",
    "G GAIN ACH",
    "B GAIN ACH",
    "R GAIN BCH",
    "G GAIN BCH",
    "B GAIN BCH",
    "RGB GAIN OFFSET BCH",
    "R WHITE CLIP LEVEL",
    "B WHITE CLIP LEVEL",
    "V DETAIL LEVEL",
    "V DETAIL FREQUENCY",
    "LEVEL DEPENDENT",
}


def _transform_reset_entry(label, cmd, addr, data):
    if label.startswith(_SKIP_LABEL_PREFIXES):
        return None
    if label in {"MATRIX COLOUR CORRECT", "MATRIX COLOUR CORRECT [PDF ALT]"}:
        return None
    if label in _REMOVE_RESET_LABELS:
        return None
    if label == "PRESET MATRIX":
        return None
    if label in {"R GAMMA", "B GAMMA"}:
        return None
    if label in _MATRIX_USER_VALUES:
        matrix_cmd, matrix_addr, matrix_data = _MATRIX_USER_VALUES[label]
        return label, matrix_cmd, matrix_addr, matrix_data
    if label.endswith("_P") and label.startswith("MATRIX("):
        return None
    if label == "SHUTTER":
        return "SHUTTER", "OSJ", "03", "0"
    if label == "GAMMA MODE":
        return "GAMMA MODE", "OSE", "72", "0"
    if label == "CHROMA LEVEL":
        return "CHROMA LEVEL", "OSD", "B0", "80"
    if label == "BLACK GAMMA":
        return "BLACK GAMMA", "OSA", "07", "80"
    if label == "KNEE R POINT":
        return "KNEE POINT", "OSA", "20", "80"
    if label == "KNEE B POINT":
        return None
    if label == "KNEE R SLOPE":
        return "KNEE SLOPE", "OSA", "24", "00"
    if label == "KNEE B SLOPE":
        return None
    if label == "MASTER WHITE CLIP LEVEL":
        return "MASTER WHITE CLIP LEVEL", "OSA", "2A", "0A"
    return label, cmd, addr, data


RESET_COMMANDS = []
for _label, _cmd, _addr, _data in _UE160_RESET_COMMANDS:
    _entry = _transform_reset_entry(_label, _cmd, _addr, _data)
    if _entry is not None:
        RESET_COMMANDS.append(_entry)

RESET_COMMANDS.extend([
    ("CHROMA LEVEL [PDF ALT]", "OSD", "B0", "80"),
    ("BLACK GAMMA [PDF ALT]",  "OSA", "07", "80"),
    ("SHUTTER [PDF ALT]",      "OSJ", "03", "0"),
])

# ---------------------------------------------------------------------------
# UI definition
# ---------------------------------------------------------------------------

UI_BUTTONS = {
    "auto_focus":    {"on": "OAF:1",    "off": "OAF:0"},
    "auto_iris":     {"on": "ORS:1",    "off": "ORS:0"},
    "awb_black":     {"cmd": "OAS"},
    "aww_white":     {"cmd": "OWS"},
    "drs":           {"on": "OSE:33:1", "off": "OSE:33:0"},
    "gamma":         {"on": "OSA:0A:1", "off": "OSA:0A:0"},
    "knee":          {"on": "OSA:2D:1", "off": "OSA:2D:0"},
    "linear_matrix": {"on": "OSL:6C:1", "off": "OSL:6C:0"},
    "matrix":        {"on": "OSA:84:1", "off": "OSA:84:0"},
    "white_clip":    {"on": "OSA:2E:1", "off": "OSA:2E:0"},
}

UI_BUTTON_LABELS = {
    "auto_focus":    "Auto Focus",
    "auto_iris":     "Auto Iris",
    "drs":           "DRS",
    "gamma":         "Gamma",
    "knee":          "Knee",
    "linear_matrix": "Linear Matrix",
    "matrix":        "Matrix",
    "white_clip":    "White Clip",
    "awb_black":     "ABB (Black)",
    "aww_white":     "AWW (White)",
}

UI_LAYOUT = [
    ("knee",       "drs",        "gamma",         "color_temp"),
    ("white_clip", "auto_iris",  "auto_focus",    None),
    ("matrix",     "linear_matrix", "awb_black",  None),
]

UI_DROPDOWNS = {
    "color_temp": [
        ("Select White Balance Mode", None),
        ("White Balance is AWW A",    "OAW:0"),
        ("White Balance is AWW B",    "OAW:1"),
    ],
}

AWW_REQUIRED_OPTIONS = ["White Balance is AWW A", "White Balance is AWW B"]

BALANCE_COMPLETION_QUERIES = {
    "awb_black": "QAW",
    "aww_white": "QAW",
}

UI_FEATURE_QUERIES = {
    "auto_focus":    "QAF",
    "auto_iris":     "QRS",
    "drs":           "QSE:33",
    "gamma":         "QSA:0A",
    "knee":          "QSA:2D",
    "linear_matrix": "QSL:6C",
    "matrix":        "QSA:84",
    "white_clip":    "QSA:2E",
}

UI_DROPDOWN_QUERIES = {
    "color_temp": "QAW",
}

POST_RESET_FEATURE_STATES = [
    ("auto_iris",  True),
    ("auto_focus", False),
    ("drs",        True),
    ("knee",       True),
    ("white_clip", False),
]

POST_RESET_DROPDOWN_DEFAULTS = {
    "color_temp": "White Balance is AWW A",
}

POST_RESET_STATUS_QUERIES = [
    ("Auto Iris",  "QRS"),
    ("Auto Focus", "QAF"),
    ("DRS",        "QSE:33"),
    ("Knee",       "QSA:2D"),
    ("White Clip", "QSA:2E"),
    ("White Balance Mode", "QAW"),
]

# ---------------------------------------------------------------------------
# Command key sets
# ---------------------------------------------------------------------------

_ATW_KEYS            = {("OSJ", "0D"), ("OSJ", "0E")}
_DETAIL_KEYS         = {("OSA", "30")}
_MASTER_PEDESTAL_KEYS = {("OSJ", "0F")}
_WHITE_CLIP_LEVEL_KEYS = {("OSA", "2A")}
_COLOR_CORRECT_KEYS  = {
    ("OSD", "80"), ("OSD", "81"), ("OSD", "82"), ("OSD", "83"),
    ("OSD", "84"), ("OSD", "85"), ("OSD", "86"), ("OSD", "87"),
    ("OSD", "88"), ("OSD", "89"), ("OSD", "8A"), ("OSD", "8B"),
    ("OSD", "8C"), ("OSD", "8D"), ("OSD", "8E"), ("OSD", "8F"),
    ("OSD", "90"), ("OSD", "91"), ("OSD", "92"), ("OSD", "93"),
    ("OSD", "94"), ("OSD", "95"), ("OSD", "96"), ("OSD", "97"),
}

# ---------------------------------------------------------------------------
# Reset logic
# ---------------------------------------------------------------------------

def _prepare_reset_environment(context) -> dict:
    prep = {
        "gain_default":   False,
        "super_gain_off": False,
        "nd_through":     False,
        "vlog_off":       False,
        "hdr_off":        False,
    }

    context.logging.info("Reset prep: setting GAIN to default")
    prep["gain_default"] = _send_set_command(context, "GAIN", "OGU:08")

    context.logging.info("Reset prep: setting SUPER GAIN OFF")
    prep["super_gain_off"] = _send_set_command(context, "SUPER GAIN", "OSI:28:0")

    context.logging.info("Reset prep: setting ND FILTER THROUGH")
    prep["nd_through"] = _send_set_command(context, "ND FILTER", "OFT:0")

    context.logging.info("Reset prep: setting V-LOG OFF")
    prep["vlog_off"] = _ensure_dropdown_value(
        context, "V-LOG", "QSJ:56", "OSJ:56", "0"
    )

    context.logging.info("Reset prep: setting HDR OFF")
    prep["hdr_off"] = _ensure_dropdown_value(
        context, "HDR", "QSJ:2C", "OSJ:2C", "0"
    )

    return prep


def _run_reset_sequence(context, prep: dict) -> None:
    entries = _build_entries(RESET_COMMANDS)

    atw_mode       = [e for e in entries if e["label"] == "ATW"]
    atw            = _filter_entries(entries, _ATW_KEYS)
    camera_gain    = [e for e in entries if e["label"] == "CAMERA GAIN"]
    white_clip_lvl = _filter_entries(entries, _WHITE_CLIP_LEVEL_KEYS)
    detail         = _filter_entries(entries, _DETAIL_KEYS)
    pedestal       = _filter_entries(entries, _MASTER_PEDESTAL_KEYS)
    color_correct  = _filter_entries(entries, _COLOR_CORRECT_KEYS)

    handled: set[int] = set()

    def _mark(*groups):
        for g in groups:
            for e in g:
                handled.add(e["index"])

    if atw_mode:
        context.logging.info("Reset prep: setting WHITE BALANCE MODE to ATW")
        _send_set_command(context, "WHITE BALANCE MODE (ATW)", "OAW:0")
        _mark(atw_mode)

    if atw:
        _apply_reset_commands(context, atw)
        _mark(atw)

    if atw_mode:
        context.logging.info("Reset prep: setting WHITE BALANCE MODE to AWC A")
        _send_set_command(context, "WHITE BALANCE MODE (AWC A)", "OAW:1")

    if camera_gain:
        if _send_set_command(context, "CAMERA GAIN", "OGU:08"):
            context.logging.info("[CAMERA GAIN] -> Set to Standard")
        _mark(camera_gain)

    context.logging.info("Reset prep: setting pedestal defaults (UE150A)")
    pedestal_ok = (
        _send_set_command(context, "R PEDESTAL", "ORP:096")
        and _send_set_command(context, "G PEDESTAL", "OSJ:10:096")
        and _send_set_command(context, "B PEDESTAL", "OBP:096")
    )
    if pedestal_ok:
        context.logging.info("[PEDESTAL] -> Set to Standard")

    context.logging.info("Reset prep: setting gain defaults (UE150A)")
    gain_ok = (
        _send_set_command(context, "R GAIN", "OSG:39:800")
        and _send_set_command(context, "B GAIN", "OSG:3A:800")
    )
    if gain_ok:
        context.logging.info("[GAIN] -> Set to Standard")

    blockers_ready = prep["vlog_off"] and prep["hdr_off"]

    if color_correct:
        if not blockers_ready:
            _skip_reset_commands(
                context, color_correct,
                "global blockers (V-LOG/HDR) could not be confirmed OFF",
            )
        else:
            matrix_user_ready = _ensure_dropdown_value(
                context, "MATRIX TYPE", "QSE:31", "OSE:31", "3"
            )
            adaptive_matrix_off_ready = _ensure_dropdown_value(
                context, "ADAPTIVE MATRIX", "QSJ:4F", "OSJ:4F", "0"
            )
            if matrix_user_ready and adaptive_matrix_off_ready:
                _apply_reset_commands(context, color_correct)
            else:
                _skip_reset_commands(
                    context, color_correct,
                    "MATRIX TYPE=USER and ADAPTIVE MATRIX=OFF could not be confirmed",
                )
        _mark(color_correct)

    if detail:
        if blockers_ready:
            _apply_reset_commands(context, detail)
        else:
            _skip_reset_commands(
                context, detail,
                "global blockers (V-LOG/HDR) could not be confirmed OFF",
            )
        _mark(detail)

    if pedestal:
        if blockers_ready:
            _apply_reset_commands(context, pedestal)
        else:
            _skip_reset_commands(
                context, pedestal,
                "global blockers (V-LOG/HDR) could not be confirmed OFF",
            )
        _mark(pedestal)

    if white_clip_lvl:
        if blockers_ready and _send_set_command(context, "WHITE CLIP", "OSA:2E:1"):
            _apply_reset_commands(context, white_clip_lvl)
            _send_set_command(context, "WHITE CLIP", "OSA:2E:0")
        else:
            _skip_reset_commands(
                context, white_clip_lvl,
                "WHITE CLIP could not be enabled or global blockers not cleared",
            )
        _mark(white_clip_lvl)

    remaining = [e for e in entries if e["index"] not in handled]
    _apply_reset_commands(context, remaining)


def run_reset(context) -> None:
    prep = _prepare_reset_environment(context)
    _run_reset_sequence(context, prep)
