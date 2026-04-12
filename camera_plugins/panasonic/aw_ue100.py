"""
camera_plugins/panasonic/aw_ue100.py — Panasonic AW-UE100

Migrated from camera_types/camera_aw_ue100.py.
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

CAMERA_ID    = "AW-UE100"
DISPLAY_NAME = "Panasonic AW-UE100"

RESET_COMMANDS = [
    ("ATW TARGET R", "OSJ", "0D", "80"),
    ("ATW TARGET B", "OSJ", "0E", "80"),
    ("ATW SPEED", "OSI", "25", "0"),
    ("GAMMA MODE", "OSE", "72", "0"),
    ("GAMMA", "OSA", "6A", "76"),
    ("BLACK GAMMA", "OSA", "07", "80"),
    ("BLACK GAMMA RANGE", "OSJ", "1B", "1"),
    ("MATRIX TYPE", "OSE", "31", "0"),
    ("ADAPTIVE MATRIX", "OSJ", "4F", "0"),
    ("DRS", "OSE", "33", "0"),
    ("CHROMA LEVEL", "OSD", "B0", "80"),
    ("CHROMA PHASE", "OSJ", "0B", "80"),
    ("KNEE MODE", "OSA", "2D", "1"),
    ("KNEE POINT", "OSA", "20", "80"),
    ("KNEE SLOPE", "OSA", "24", "63"),
    ("KNEE MODE", "OSA", "2D", "0"),
    ("WHITE CLIP", "OSA", "2E", "1"),
    ("WHITE CLIP LEVEL", "OSA", "2A", "13"),
    ("WHITE CLIP", "OSA", "2E", "0"),
    ("DNR", "OSD", "3A", "00"),
    ("MASTER DETAIL", "OSA", "30", "80"),
    ("DETAIL CORING", "OSJ", "12", "0F"),
    ("V DETAIL LEVEL", "OSD", "A1", "80"),
    ("DETAIL FREQUENCY", "OSD", "A2", "80"),
    ("LEVEL DEPEND", "OSJ", "13", "80"),
    ("KNEE APERTURE LEVEL", "OSG", "3F", "02"),
    ("DETAIL GAIN (+)", "OSA", "38", "80"),
    ("DETAIL GAIN (-)", "OSA", "39", "80"),
    ("COLOR CORRECTION G SATURATION", "OSD", "8E", "80"),
    ("COLOR CORRECTION G_CY SATURATION", "OSD", "90", "80"),
    ("COLOR CORRECTION CY SATURATION", "OSD", "92", "80"),
    ("COLOR CORRECTION CY_B SATURATION", "OSD", "94", "80"),
    ("COLOR CORRECTION B SATURATION", "OSD", "96", "80"),
    ("COLOR CORRECTION B_MG SATURATION", "OSD", "80", "80"),
    ("COLOR CORRECTION MG SATURATION", "OSD", "82", "80"),
    ("COLOR CORRECTION MG_R SATURATION", "OSD", "84", "80"),
    ("COLOR CORRECTION R SATURATION", "OSD", "86", "80"),
    ("COLOR CORRECTION R_YE SATURATION", "OSD", "88", "80"),
    ("COLOR CORRECTION YE SATURATION", "OSD", "8A", "80"),
    ("COLOR CORRECTION YE_G SATURATION", "OSD", "8C", "80"),
    ("COLOR CORRECTION G PHASE", "OSD", "8F", "80"),
    ("COLOR CORRECTION G_CY PHASE", "OSD", "91", "80"),
    ("COLOR CORRECTION CY PHASE", "OSD", "93", "80"),
    ("COLOR CORRECTION CY_B PHASE", "OSD", "95", "80"),
    ("COLOR CORRECTION B PHASE", "OSD", "97", "80"),
    ("COLOR CORRECTION B_MG PHASE", "OSD", "81", "80"),
    ("COLOR CORRECTION MG PHASE", "OSD", "83", "80"),
    ("COLOR CORRECTION MG_R PHASE", "OSD", "85", "80"),
    ("COLOR CORRECTION R PHASE", "OSD", "87", "80"),
    ("COLOR CORRECTION R_YE PHASE", "OSD", "89", "80"),
    ("COLOR CORRECTION YE PHASE", "OSD", "8B", "80"),
    ("COLOR CORRECTION YE_G PHASE", "OSD", "8D", "80"),
    ("MASTER PEDESTAL", "OSJ", "0F", "800"),
    ("PEDESTAL OFFSET", "OSJ", "11", "0"),
    ("PICTURE LEVEL", "OSD", "48", "32"),
    ("AWB GAIN OFFSET", "OSJ", "0C", "0"),
    ("SKIN TONE DETAIL", "OSA", "40", "1"),
    ("SKIN DETAIL EFFECT", "OSD", "A3", "90"),
    ("SKIN TONE DETAIL", "OSA", "40", "0"),
]

UI_BUTTONS = {
    "auto_focus": {"on": "OAF:1",    "off": "OAF:0"},
    "auto_iris":  {"on": "ORS:1",    "off": "ORS:0"},
    "awb_black":  {"cmd": "OAS"},
    "aww_white":  {"cmd": "OWS"},
    "drs":        {"on": "OSE:33:1", "off": "OSE:33:0"},
    "knee":       {"on": "OSA:2D:1", "off": "OSA:2D:0"},
    "white_clip": {"on": "OSA:2E:1", "off": "OSA:2E:0"},
}

UI_BUTTON_LABELS = {
    "auto_focus": "Auto Focus",
    "auto_iris":  "Auto Iris",
    "drs":        "DRS",
    "knee":       "Knee",
    "white_clip": "White Clip",
    "awb_black":  "ABB (Black)",
    "aww_white":  "AWW (White)",
}

UI_LAYOUT = [
    ("knee",       "drs",       "auto_iris",  "gamma"),
    ("white_clip", "auto_focus","awb_black",  "color_temp"),
]

UI_DROPDOWNS = {
    "color_temp": [
        ("White Balance is AWB A",       "OAW:1"),
        ("White Balance is AWB B",       "OAW:2"),
        ("White Balance is Preset 3200K","OAW:4"),
        ("White Balance is Preset 5600K","OAW:5"),
        ("White Balance is VAR",         "OAW:9"),
        ("White Balance is ATW",         "OAW:0"),
    ],
    "gamma": [
        ("Gamma is HD",         "OSE:72:0"),
        ("Gamma is FILMLIKE 1", "OSE:72:2"),
        ("Gamma is FILMLIKE 2", "OSE:72:3"),
        ("Gamma is FILMLIKE 3", "OSE:72:4"),
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
    "knee":       "QSA:2D",
    "white_clip": "QSA:2E",
}

UI_DROPDOWN_QUERIES = {
    "color_temp": "QAW",
    "gamma":      "QSE:72",
}

POST_RESET_FEATURE_STATES = [
    ("auto_iris",  True),
    ("auto_focus", False),
    ("drs",        False),
    ("knee",       False),
    ("white_clip", False),
]

POST_RESET_DROPDOWN_DEFAULTS = {
    "color_temp": "White Balance is ATW",
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

_ATW_KEYS          = {("OSJ", "0D"), ("OSJ", "0E")}
_COLOR_CORRECT_KEYS = {
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
        "nd_through":     False,
        "shutter_off":    False,
        "detail_on":      False,
        "r_pedestal_zero": False,
        "g_pedestal_zero": False,
        "b_pedestal_zero": False,
    }

    context.logging.info("Reset prep: setting GAIN to 0dB")
    prep["gain_default"] = _ensure_dropdown_value(
        context, "GAIN", "QGU", "OGU", "08"
    )

    context.logging.info("Reset prep: setting ND FILTER THROUGH")
    prep["nd_through"] = _ensure_dropdown_value(
        context, "ND FILTER", "QFT", "OFT", "0"
    )

    context.logging.info("Reset prep: setting SHUTTER MODE OFF")
    prep["shutter_off"] = _ensure_dropdown_value(
        context, "SHUTTER MODE", "QSJ:03", "OSJ:03", "0"
    )

    context.logging.info("Reset prep: setting DETAIL ON")
    prep["detail_on"] = _ensure_dropdown_value(
        context, "DETAIL", "QDT", "ODT", "1"
    )

    context.logging.info("Reset prep: setting R PEDESTAL to 0")
    prep["r_pedestal_zero"] = _ensure_dropdown_value(
        context, "R PEDESTAL", "QRP", "ORP", "096"
    )

    context.logging.info("Reset prep: setting G PEDESTAL to 0")
    prep["g_pedestal_zero"] = _ensure_dropdown_value(
        context, "G PEDESTAL", "QSJ:10", "OSJ:10", "096"
    )

    context.logging.info("Reset prep: setting B PEDESTAL to 0")
    prep["b_pedestal_zero"] = _ensure_dropdown_value(
        context, "B PEDESTAL", "QBP", "OBP", "096"
    )

    return prep


def _run_reset_sequence(context, _prep: dict) -> None:
    entries = _build_entries(RESET_COMMANDS)

    atw           = _filter_entries(entries, _ATW_KEYS)
    color_correct = _filter_entries(entries, _COLOR_CORRECT_KEYS)

    handled: set[int] = set()

    def _mark(*groups):
        for g in groups:
            for e in g:
                handled.add(e["index"])

    if atw:
        _ensure_dropdown_value(context, "WHITE BALANCE MODE", "QAW", "OAW", "0")  # ATW
        _apply_reset_commands(context, atw)
        _mark(atw)

    if color_correct:
        _ensure_dropdown_value(context, "MATRIX TYPE", "QSE:31", "OSE:31", "3")  # USER
        _apply_reset_commands(context, color_correct)
        _send_set_command(context, "MATRIX TYPE", "OSE:31:0")  # NORMAL
        _mark(color_correct)

    remaining = [e for e in entries if e["index"] not in handled]
    _apply_reset_commands(context, remaining)


def run_reset(context) -> None:
    prep = _prepare_reset_environment(context)
    _run_reset_sequence(context, prep)
