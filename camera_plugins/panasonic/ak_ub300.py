"""
camera_plugins/panasonic/ak_ub300.py — Panasonic AK-UB300

Studio box 4K camera (B4 lens mount).
Distinct features vs PTZ line: selectable gain regions (LOW/MID/HIGH),
Super Gain, dual matrix tables (A/B), skin tone detail, haze reduction,
HLG gamma modes, and 4K crop area selection.
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

CAMERA_ID         = "AK-UB300"
CAMERA_ID_ALIASES = ["AK-UB300GJ", "AK-UB300EJ"]
DISPLAY_NAME      = "Panasonic AK-UB300"

# ---------------------------------------------------------------------------
# RESET_COMMANDS
# ---------------------------------------------------------------------------

RESET_COMMANDS = [
    # Gain — AK-UB300 uses OGS to select the active gain region (L/M/H)
    # and OGU to set the level within that region.
    # Reset to GAIN SELECT=M (0dB region), level=0dB.
    ("GAIN SELECT",                      "OGS", "01", "1"),    # 0=LOW 1=MID 2=HIGH
    ("GAIN",                             "OGU", "08", "08"),   # 0dB within MID region
    ("SUPER GAIN",                       "OSI", "28", "0"),    # Super Gain OFF
    # White balance ATW targets
    ("ATW TARGET R",                     "OSJ", "0D", "80"),
    ("ATW TARGET B",                     "OSJ", "0E", "80"),
    ("ATW SPEED",                        "OSI", "25", "0"),
    # Gamma — HLG values: 5=HLG(BT.2100), 6=HLG(USER)
    ("GAMMA MODE",                       "OSE", "72", "0"),    # 0=HD
    ("GAMMA",                            "OSA", "6A", "76"),
    ("BLACK GAMMA",                      "OSA", "07", "80"),
    ("BLACK GAMMA RANGE",                "OSJ", "1B", "1"),
    # Matrix — table A is active; table select via OSE:50 (0=A, 1=B)
    ("MATRIX TABLE",                     "OSE", "50", "0"),    # 0=A 1=B
    ("MATRIX TYPE",                      "OSE", "31", "0"),
    ("ADAPTIVE MATRIX",                  "OSJ", "4F", "0"),
    # DRS
    ("DRS",                              "OSE", "33", "0"),
    # Chroma
    ("CHROMA LEVEL",                     "OSD", "B0", "80"),
    ("CHROMA PHASE",                     "OSJ", "0B", "80"),
    # Knee
    ("KNEE MODE",                        "OSA", "2D", "1"),
    ("KNEE POINT",                       "OSA", "20", "80"),
    ("KNEE SLOPE",                       "OSA", "24", "63"),
    ("KNEE MODE",                        "OSA", "2D", "0"),
    # White clip
    ("WHITE CLIP",                       "OSA", "2E", "1"),
    ("WHITE CLIP LEVEL",                 "OSA", "2A", "13"),
    ("WHITE CLIP",                       "OSA", "2E", "0"),
    # Detail
    ("DNR",                              "OSD", "3A", "00"),
    ("MASTER DETAIL",                    "OSA", "30", "80"),
    ("DETAIL CORING",                    "OSJ", "12", "0F"),
    ("V DETAIL LEVEL",                   "OSD", "A1", "80"),
    ("DETAIL FREQUENCY",                 "OSD", "A2", "80"),
    ("LEVEL DEPEND",                     "OSJ", "13", "80"),
    ("KNEE APERTURE LEVEL",              "OSG", "3F", "02"),
    ("DETAIL GAIN (+)",                  "OSA", "38", "80"),
    ("DETAIL GAIN (-)",                  "OSA", "39", "80"),
    # Haze reduction (box camera feature)
    ("HAZE REDUCTION",                   "OSI", "50", "0"),    # 0=OFF
    # 6-element linear matrix (applied when MATRIX TYPE=USER)
    ("MATRIX(R-G)",                      "OSD", "A4", "80"),
    ("MATRIX(R-B)",                      "OSD", "A5", "80"),
    ("MATRIX(G-R)",                      "OSD", "A6", "80"),
    ("MATRIX(G-B)",                      "OSD", "A7", "80"),
    ("MATRIX(B-R)",                      "OSD", "A8", "80"),
    ("MATRIX(B-G)",                      "OSD", "A9", "80"),
    # 12-zone colour correction — saturation
    ("COLOR CORRECTION G SATURATION",    "OSD", "8E", "80"),
    ("COLOR CORRECTION G_CY SATURATION", "OSD", "90", "80"),
    ("COLOR CORRECTION CY SATURATION",   "OSD", "92", "80"),
    ("COLOR CORRECTION CY_B SATURATION", "OSD", "94", "80"),
    ("COLOR CORRECTION B SATURATION",    "OSD", "96", "80"),
    ("COLOR CORRECTION B_MG SATURATION", "OSD", "80", "80"),
    ("COLOR CORRECTION MG SATURATION",   "OSD", "82", "80"),
    ("COLOR CORRECTION MG_R SATURATION", "OSD", "84", "80"),
    ("COLOR CORRECTION R SATURATION",    "OSD", "86", "80"),
    ("COLOR CORRECTION R_YE SATURATION", "OSD", "88", "80"),
    ("COLOR CORRECTION YE SATURATION",   "OSD", "8A", "80"),
    ("COLOR CORRECTION YE_G SATURATION", "OSD", "8C", "80"),
    # 12-zone colour correction — phase
    ("COLOR CORRECTION G PHASE",         "OSD", "8F", "80"),
    ("COLOR CORRECTION G_CY PHASE",      "OSD", "91", "80"),
    ("COLOR CORRECTION CY PHASE",        "OSD", "93", "80"),
    ("COLOR CORRECTION CY_B PHASE",      "OSD", "95", "80"),
    ("COLOR CORRECTION B PHASE",         "OSD", "97", "80"),
    ("COLOR CORRECTION B_MG PHASE",      "OSD", "81", "80"),
    ("COLOR CORRECTION MG PHASE",        "OSD", "83", "80"),
    ("COLOR CORRECTION MG_R PHASE",      "OSD", "85", "80"),
    ("COLOR CORRECTION R PHASE",         "OSD", "87", "80"),
    ("COLOR CORRECTION R_YE PHASE",      "OSD", "89", "80"),
    ("COLOR CORRECTION YE PHASE",        "OSD", "8B", "80"),
    ("COLOR CORRECTION YE_G PHASE",      "OSD", "8D", "80"),
    # Pedestal / picture level
    ("MASTER PEDESTAL",                  "OSJ", "0F", "800"),
    ("PEDESTAL OFFSET",                  "OSJ", "11", "0"),
    ("PICTURE LEVEL",                    "OSD", "48", "32"),
    ("AWB GAIN OFFSET",                  "OSJ", "0C", "0"),
    # Skin tone detail
    ("SKIN TONE DETAIL",                 "OSA", "40", "1"),
    ("SKIN DETAIL EFFECT",               "OSD", "A3", "90"),
    ("SKIN TONE DETAIL",                 "OSA", "40", "0"),
]

# ---------------------------------------------------------------------------
# UI definition
# ---------------------------------------------------------------------------

UI_BUTTONS = {
    "auto_iris":   {"on": "ORS:1",    "off": "ORS:0"},
    "awb_black":   {"cmd": "OAS"},
    "aww_white":   {"cmd": "OWS"},
    "drs":         {"on": "OSE:33:1", "off": "OSE:33:0"},
    "knee":        {"on": "OSA:2D:1", "off": "OSA:2D:0"},
    "white_clip":  {"on": "OSA:2E:1", "off": "OSA:2E:0"},
    "super_gain":  {"on": "OSI:28:1", "off": "OSI:28:0"},
}

UI_BUTTON_LABELS = {
    "auto_iris":   "Auto Iris",
    "drs":         "DRS",
    "knee":        "Knee",
    "white_clip":  "White Clip",
    "awb_black":   "ABB (Black)",
    "aww_white":   "AWW (White)",
    "super_gain":  "Super Gain",
}

UI_LAYOUT = [
    ("knee",       "drs",       "auto_iris",  "gamma"),
    ("white_clip", "super_gain","awb_black",  "color_temp"),
    (None,         None,        None,         "gain_select"),
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
    "gamma": [
        ("Gamma is HD",         "OSE:72:0"),
        ("Gamma is FILMLIKE 1", "OSE:72:2"),
        ("Gamma is FILMLIKE 2", "OSE:72:3"),
        ("Gamma is FILMLIKE 3", "OSE:72:4"),
        ("Gamma is HLG",        "OSE:72:5"),
        ("Gamma is HLG USER",   "OSE:72:6"),
    ],
    "gain_select": [
        ("Gain Region is LOW",  "OGS:01:0"),
        ("Gain Region is MID",  "OGS:01:1"),
        ("Gain Region is HIGH", "OGS:01:2"),
    ],
}

AWW_REQUIRED_OPTIONS = ["White Balance is AWB A", "White Balance is AWB B"]

BALANCE_COMPLETION_QUERIES = {
    "awb_black": "QAW",
    "aww_white": "QAW",
}

UI_FEATURE_QUERIES = {
    "auto_iris":  "QRS",
    "drs":        "QSE:33",
    "knee":       "QSA:2D",
    "white_clip": "QSA:2E",
    "super_gain": "QSI:28",
}

UI_DROPDOWN_QUERIES = {
    "color_temp":  "QAW",
    "gamma":       "QSE:72",
    "gain_select": "QGS:01",
}

POST_RESET_FEATURE_STATES = [
    ("auto_iris",  True),
    ("drs",        False),
    ("knee",       False),
    ("white_clip", False),
    ("super_gain", False),
]

POST_RESET_DROPDOWN_DEFAULTS = {
    "color_temp":  "White Balance is ATW",
    "gamma":       "Gamma is HD",
    "gain_select": "Gain Region is MID",
}

POST_RESET_STATUS_QUERIES = [
    ("Auto Iris",    "QRS"),
    ("DRS",          "QSE:33"),
    ("Knee",         "QSA:2D"),
    ("White Clip",   "QSA:2E"),
    ("Super Gain",   "QSI:28"),
    ("White Balance Mode", "QAW"),
    ("Gamma Mode",   "QSE:72"),
    ("Gain Region",  "QGS:01"),
]

# ---------------------------------------------------------------------------
# Command key sets
# ---------------------------------------------------------------------------

_ATW_KEYS = {("OSJ", "0D"), ("OSJ", "0E")}

_MATRIX_KEYS = {
    ("OSD", "A4"), ("OSD", "A5"), ("OSD", "A6"),
    ("OSD", "A7"), ("OSD", "A8"), ("OSD", "A9"),
}

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
        "gain_select_mid": False,
        "gain_default":    False,
        "super_gain_off":  False,
        "nd_through":      False,
        "hlg_off":         False,
    }

    context.logging.info("Reset prep: setting GAIN SELECT to MID")
    prep["gain_select_mid"] = _ensure_dropdown_value(
        context, "GAIN SELECT", "QGS:01", "OGS:01", "1"
    )

    context.logging.info("Reset prep: setting GAIN to 0dB")
    prep["gain_default"] = _ensure_dropdown_value(
        context, "GAIN", "QGU", "OGU", "08"
    )

    context.logging.info("Reset prep: setting SUPER GAIN OFF")
    prep["super_gain_off"] = _ensure_dropdown_value(
        context, "SUPER GAIN", "QSI:28", "OSI:28", "0"
    )

    context.logging.info("Reset prep: setting ND FILTER THROUGH")
    prep["nd_through"] = _ensure_dropdown_value(
        context, "ND FILTER", "QFT", "OFT", "0"
    )

    context.logging.info("Reset prep: setting GAMMA MODE to HD (disabling HLG)")
    prep["hlg_off"] = _ensure_dropdown_value(
        context, "GAMMA MODE", "QSE:72", "OSE:72", "0"
    )

    return prep


def _run_reset_sequence(context, prep: dict) -> None:
    entries = _build_entries(RESET_COMMANDS)

    atw           = _filter_entries(entries, _ATW_KEYS)
    matrix        = _filter_entries(entries, _MATRIX_KEYS)
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

    # Matrix elements and colour correction both require MATRIX TYPE=USER
    hlg_blocker = not prep.get("hlg_off", False)
    if matrix or color_correct:
        if hlg_blocker:
            _skip_reset_commands(
                context, matrix + color_correct,
                "GAMMA MODE could not be confirmed non-HLG",
            )
        else:
            matrix_user_ok = _ensure_dropdown_value(
                context, "MATRIX TYPE", "QSE:31", "OSE:31", "3"
            )
            if matrix_user_ok:
                if matrix:
                    _apply_reset_commands(context, matrix)
                if color_correct:
                    _apply_reset_commands(context, color_correct)
                _send_set_command(context, "MATRIX TYPE", "OSE:31:0")
            else:
                _skip_reset_commands(
                    context, matrix + color_correct,
                    "MATRIX TYPE could not be set to USER",
                )
        _mark(matrix, color_correct)

    remaining = [e for e in entries if e["index"] not in handled]
    _apply_reset_commands(context, remaining)


def run_reset(context) -> None:
    prep = _prepare_reset_environment(context)
    _run_reset_sequence(context, prep)
