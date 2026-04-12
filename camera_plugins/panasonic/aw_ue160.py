"""
camera_plugins/panasonic/aw_ue160.py — Panasonic AW-UE160

Migriert aus camera_types/camera_aw_ue160.py.
Helfer-Funktionen kommen aus camera_plugins/panasonic/base.py.
context.send_command() gibt str | None zurück (neues ResetContext-Interface).
"""

from camera_plugins.panasonic.base import (
    PROTOCOL,
    apply_reset_commands as _apply_reset_commands,
    build_entries as _build_entries,
    ensure_dropdown_value as _ensure_dropdown_value,
    ensure_feature_state as _ensure_feature_state,
    extract_value as _extract_value,
    filter_entries as _filter_entries,
    query_raw as _query_raw,
    send_set_command as _send_set_command,
    skip_reset_commands as _skip_reset_commands,
)

CAMERA_ID    = "AW-UE160"
DISPLAY_NAME = "Panasonic AW-UE160"

RESET_COMMANDS = [
    ("CAMERA GAIN", "OSL", "25", "08"),
    ("ATW", "OSL", "2A", "1"),
    ("ATW TARGET R", "OSJ", "0D", "80"),
    ("ATW TARGET B", "OSJ", "0E", "80"),
    ("ATW", "OSL", "2A", "0"),
    ("CHROMA LEVEL", "OSG", "93", "1"),
    ("CHROMA LEVEL", "OSL", "B0", "80"),
    ("CHROMA LEVEL", "OSG", "93", "0"),
    ("MASTER FLARE", "OSL", "40", "800"),
    ("R FLARE", "OSL", "41", "800"),
    ("G FLARE", "OSL", "42", "800"),
    ("B FLARE", "OSL", "43", "800"),
    ("R GAMMA", "OSI", "35", "80"),
    ("B GAMMA", "OSI", "36", "80"),
    ("GAMMA MODE", "OSJ", "D7", "00"),
    ("MASTER GAMMA", "OSA", "6A", "76"),
    ("BLACK GAMMA", "OSA", "0B", "1"),
    ("MASTER BLACK GAMMA", "OSA", "07", "80"),
    ("BLACK GAMMA RANGE", "OSJ", "1B", "1"),
    ("BLACK GAMMA", "OSA", "0B", "0"),
    ("KNEE", "OSA", "2D", "1"),
    ("KNEE R POINT", "OSA", "22", "80"),
    ("KNEE B POINT", "OSA", "23", "80"),
    ("KNEE R SLOPE", "OSA", "26", "80"),
    ("KNEE B SLOPE", "OSA", "27", "80"),
    ("KNEE", "OSA", "2D", "0"),
    ("MASTER DETAIL", "OSA", "30", "80"),
    ("V DETAIL LEVEL", "OSJ", "17", "80"),
    ("V DETAIL FREQUENCY", "OSL", "53", "00"),
    ("LEVEL DEPENDENT", "OSD", "26", "00"),
    ("KNEE APERTURE LEVEL", "OSG", "3F", "02"),
    ("DETAIL GAIN (+)", "OSA", "38", "80"),
    ("DETAIL GAIN (-)", "OSA", "39", "80"),
    ("DNR", "OSD", "3A", "00"),
    ("PRESET MATRIX", "OSE", "31", "0"),
    ("MATRIX COLOUR CORRECT", "OSA", "84", "1"),
    ("MATRIX COLOUR CORRECT", "OSL", "6C", "1"),
    ("MATRIX COLOUR CORRECT", "OSA", "85", "1"),
    ("MATRIX(R-G)_N", "OSD", "2F", "1F"),
    ("MATRIX(R-G)_P", "OSL", "6F", "1F"),
    ("MATRIX(R-B)_N", "OSD", "30", "1F"),
    ("MATRIX(R-B)_P", "OSL", "70", "1F"),
    ("MATRIX(G-R)_N", "OSD", "31", "1F"),
    ("MATRIX(G-R)_P", "OSL", "71", "1F"),
    ("MATRIX(G-B)_N", "OSD", "32", "1F"),
    ("MATRIX(G-B)_P", "OSL", "72", "1F"),
    ("MATRIX(B-R)_N", "OSD", "33", "1F"),
    ("MATRIX(B-R)_P", "OSL", "73", "1F"),
    ("MATRIX(B-G)_N", "OSD", "34", "1F"),
    ("MATRIX(B-G)_P", "OSL", "74", "1F"),
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
    ("MATRIX COLOUR CORRECT", "OSA", "85", "0"),
    ("MASTER PEDESTAL", "OSJ", "0F", "800"),
    ("R PEDESTAL", "OSG", "4C", "800"),
    ("G PEDESTAL", "OSG", "4D", "800"),
    ("B PEDESTAL", "OSG", "4E", "800"),
    ("PEDESTAL OFFSET", "OSJ", "11", "0"),
    ("PICTURE LEVEL", "OSD", "48", "32"),
    ("R GAIN ACH", "OSL", "39", "800"),
    ("G GAIN ACH", "OSL", "3A", "800"),
    ("B GAIN ACH", "OSL", "3B", "800"),
    ("R GAIN BCH", "OSL", "3C", "800"),
    ("G GAIN BCH", "OSL", "3D", "800"),
    ("B GAIN BCH", "OSL", "3E", "800"),
    ("RGB GAIN OFFSET ACH", "OSJ", "0C", "0"),
    ("RGB GAIN OFFSET BCH", "OSL", "3F", "0"),
    ("SHUTTER", "OSG", "59", "0"),
    ("SKIN TONE DETAIL", "OSA", "40", "0"),
    ("MASTER WHITE CLIP LEVEL", "OSA", "2A", "6D"),
    ("R WHITE CLIP LEVEL", "OSL", "47", "80"),
    ("B WHITE CLIP LEVEL", "OSL", "48", "80"),
    ("WHITE SHADING", "OSL", "9B", "1"),
    ("WHITE SHADING W H SAW R", "OSL", "9C", "80"),
    ("WHITE SHADING W H SAW G", "OSL", "9D", "80"),
    ("WHITE SHADING W H SAW B", "OSL", "9E", "80"),
    ("WHITE SHADING W H PARA R", "OSL", "9F", "80"),
    ("WHITE SHADING W H PARA G", "OSL", "A0", "80"),
    ("WHITE SHADING W H PARA B", "OSL", "A1", "80"),
    ("WHITE SHADING W V SAW R", "OSL", "A2", "80"),
    ("WHITE SHADING W V SAW G", "OSL", "A3", "80"),
    ("WHITE SHADING W V SAW B", "OSL", "A4", "80"),
    ("WHITE SHADING W V PARA R", "OSL", "A5", "80"),
    ("WHITE SHADING W V PARA G", "OSL", "A6", "80"),
    ("WHITE SHADING W V PARA B", "OSL", "A7", "80"),
    ("WHITE SHADING", "OSL", "9B", "0"),
]

UI_BUTTONS = {
    "auto_focus":    {"on": "OAF:1",    "off": "OAF:0"},
    "auto_iris":     {"on": "ORS:1",    "off": "ORS:0"},
    "awb_black":     {"cmd": "OAS"},
    "aww_white":     {"cmd": "OWS"},
    "drs":           {"on": "OSA:0D:1", "off": "OSA:0D:0"},
    "flare":         {"on": "OSA:11:1", "off": "OSA:11:0"},
    "gamma":         {"on": "OSA:0A:1", "off": "OSA:0A:0"},
    "knee":          {"on": "OSL:45:1", "off": "OSL:45:0"},
    "linear_matrix": {"on": "OSL:6C:1", "off": "OSL:6C:0"},
    "matrix":        {"on": "OSA:84:1", "off": "OSA:84:0"},
    "white_clip":    {"on": "OSA:2E:1", "off": "OSA:2E:0"},
}

UI_LAYOUT = [
    # (btn1,        btn2,         btn3,            dropdown_key)
    ('knee',        'flare',      'gamma',          'gamma'),
    ('drs',         'auto_iris',  'auto_focus',     'color_temp'),
    ('white_clip',  'matrix',     'linear_matrix',  'linear_matrix'),
]

UI_BUTTON_LABELS = {
    "auto_focus":    "Auto Focus",
    "auto_iris":     "Auto Iris",
    "drs":           "DRS",
    "flare":         "Flare",
    "gamma":         "Gamma",
    "knee":          "Knee",
    "linear_matrix": "Linear Matrix",
    "matrix":        "Matrix",
    "white_clip":    "White Clip",
    "awb_black":     "ABB (Black)",
    "aww_white":     "AWW (White)",
}

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
        ("Gamma is HD",       "OSJ:D7:00"),
        ("Gamma is Normal",   "OSJ:D7:01"),
        ("Gamma is Cinema 1", "OSJ:D7:02"),
        ("Gamma is Cinema 2", "OSJ:D7:03"),
    ],
    "linear_matrix": [
        ("Linear Matrix Table is A", "OSA:00:0"),
        ("Linear Matrix Table is B", "OSA:00:1"),
    ],
}

AWW_REQUIRED_OPTIONS = ["White Balance is AWB A", "White Balance is AWB B"]

BALANCE_COMPLETION_QUERIES = {
    "awb_black": "QAW",
    "aww_white": "QAW",
}

BALANCE_MAX_WAIT_SECONDS = 6.0

UI_FEATURE_QUERIES = {
    "auto_focus":    "QAF",
    "auto_iris":     "QRS",
    "drs":           "QSA:0D",
    "flare":         "QSA:11",
    "gamma":         "QSA:0A",
    "knee":          "QSL:45",
    "matrix":        "QSA:84",
    "linear_matrix": "QSL:6C",
    "white_clip":    "QSA:2E",
}

UI_DROPDOWN_QUERIES = {
    "color_temp":    "QAW",
    "gamma":         "QSJ:D7",
    "linear_matrix": "QSA:00",
}

PRE_RESET_FEATURE_STATES = [
    ("matrix",        True),
    ("linear_matrix", True),
]

POST_RESET_FEATURE_STATES = [
    ("auto_iris",  True),
    ("auto_focus", True),
    ("knee",       True),
    ("flare",      True),
    ("gamma",      True),
    ("white_clip", True),
]

POST_RESET_FORCE_OFF_FEATURES = ["linear_matrix", "matrix"]

POST_RESET_DROPDOWN_DEFAULTS = {
    "color_temp": "White Balance is ATW",
    "gamma":      "Gamma is HD",
}

POST_RESET_STATUS_QUERIES = [
    ("Knee",          "QSL:45"),
    ("Flare",         "QSA:11"),
    ("Gamma",         "QSA:0A"),
    ("Auto Iris",     "QRS"),
    ("Auto Focus",    "QAF"),
    ("White Clip",    "QSA:2E"),
    ("Matrix",        "QSA:84"),
    ("Linear Matrix", "QSL:6C"),
    ("Gamma Mode",    "QSJ:D7"),
]

# ---------------------------------------------------------------------------
# Command-Key-Sets für die Reset-Sequenz
# ---------------------------------------------------------------------------

_CAMERA_GAIN_KEYS  = {("OSL", "25")}
_ATW_KEYS          = {("OSJ", "0D"), ("OSJ", "0E")}
_CHROMA_KEYS       = {("OSL", "B0")}
_GAMMA_KEYS        = {
    ("OSI", "35"), ("OSI", "36"), ("OSJ", "D7"),
    ("OSA", "6A"), ("OSA", "0B"), ("OSA", "07"), ("OSJ", "1B"),
}
_KNEE_KEYS         = {("OSA", "22"), ("OSA", "23"), ("OSA", "26"), ("OSA", "27")}
_WHITE_CLIP_KEYS   = {("OSA", "2A"), ("OSL", "47"), ("OSL", "48")}
_DETAIL_KEYS       = {
    ("OSA", "30"), ("OSJ", "17"), ("OSL", "53"),
    ("OSD", "26"), ("OSG", "3F"), ("OSA", "38"), ("OSA", "39"),
}
_DNR_KEYS          = {("OSD", "3A")}
_PEDESTAL_KEYS     = {("OSJ", "0F")}
_FLARE_KEYS        = {("OSL", "40"), ("OSL", "41"), ("OSL", "42"), ("OSL", "43")}
_MATRIX_KEYS       = {
    ("OSE", "31"), ("OSA", "84"), ("OSL", "6C"),
    ("OSD", "2F"), ("OSL", "6F"), ("OSD", "30"), ("OSL", "70"),
    ("OSD", "31"), ("OSL", "71"), ("OSD", "32"), ("OSL", "72"),
    ("OSD", "33"), ("OSL", "73"), ("OSD", "34"), ("OSL", "74"),
}
_COLOR_CORRECT_KEYS = {
    ("OSD", "80"), ("OSD", "81"), ("OSD", "82"), ("OSD", "83"),
    ("OSD", "84"), ("OSD", "85"), ("OSD", "86"), ("OSD", "87"),
    ("OSD", "88"), ("OSD", "89"), ("OSD", "8A"), ("OSD", "8B"),
    ("OSD", "8C"), ("OSD", "8D"), ("OSD", "8E"), ("OSD", "8F"),
    ("OSD", "90"), ("OSD", "91"), ("OSD", "92"), ("OSD", "93"),
    ("OSD", "94"), ("OSD", "95"), ("OSD", "96"), ("OSD", "97"),
}
_RGB_GAIN_KEYS     = {
    ("OSL", "39"), ("OSL", "3A"), ("OSL", "3B"),
    ("OSL", "3C"), ("OSL", "3D"), ("OSL", "3E"),
    ("OSJ", "0C"), ("OSL", "3F"),
}

# ---------------------------------------------------------------------------
# Reset-Ablauf
# ---------------------------------------------------------------------------

def _prepare_reset_environment(context) -> dict:
    prep = {"nd_through": False, "vlog_off": False, "hdr_off": False}

    context.logging.info("Reset prep: setting ND FILTER THROUGH")
    prep["nd_through"] = _send_set_command(context, "ND FILTER", "OFT:0")

    context.logging.info("Reset prep: setting V-LOG OFF")
    prep["vlog_off"] = _ensure_dropdown_value(
        context, "V-LOG", "QSJ:56", "OSJ:56", "0"
    )

    context.logging.info("Reset prep: setting HDR OFF")
    prep["hdr_off"] = _ensure_dropdown_value(
        context, "HDR", "QSI:2C", "OSI:2C", "0"
    )

    return prep


def _run_reset_sequence(context, prep: dict) -> None:
    entries = _build_entries(RESET_COMMANDS)

    camera_gain   = _filter_entries(entries, _CAMERA_GAIN_KEYS)
    atw           = _filter_entries(entries, _ATW_KEYS)
    chroma        = _filter_entries(entries, _CHROMA_KEYS)
    gamma         = _filter_entries(entries, _GAMMA_KEYS)
    knee          = _filter_entries(entries, _KNEE_KEYS)
    white_clip    = _filter_entries(entries, _WHITE_CLIP_KEYS)
    detail        = _filter_entries(entries, _DETAIL_KEYS)
    dnr           = _filter_entries(entries, _DNR_KEYS)
    pedestal      = _filter_entries(entries, _PEDESTAL_KEYS)
    flare         = _filter_entries(entries, _FLARE_KEYS)
    matrix        = _filter_entries(entries, _MATRIX_KEYS)
    color_correct = _filter_entries(entries, _COLOR_CORRECT_KEYS)
    rgb_gain      = _filter_entries(entries, _RGB_GAIN_KEYS)

    handled: set[int] = set()

    def _mark(*groups):
        for g in groups:
            for e in g:
                handled.add(e["index"])

    blockers_ready = prep["vlog_off"] and prep["hdr_off"]

    if camera_gain:
        _apply_reset_commands(context, camera_gain)
        _mark(camera_gain)

    if atw:
        ok = _ensure_feature_state(context, "ATW", "QSL:2A", "OSL:2A:1", True)
        if ok:
            _apply_reset_commands(context, atw)
        else:
            _skip_reset_commands(context, atw, "ATW could not be enabled")
        _mark(atw)

    if chroma:
        ok = _ensure_feature_state(context, "CHROMA LEVEL SW", "QSG:93", "OSG:93:1", True)
        if ok:
            _apply_reset_commands(context, chroma)
        else:
            _skip_reset_commands(context, chroma, "CHROMA LEVEL SW could not be enabled")
        _mark(chroma)

    if gamma:
        ok = blockers_ready and _ensure_feature_state(
            context, "GAMMA", "QSA:0A", "OSA:0A:1", True
        )
        if ok:
            _apply_reset_commands(context, gamma)
        else:
            _skip_reset_commands(
                context, gamma,
                "GAMMA could not be enabled or global blockers (V-LOG/HDR) not cleared"
            )
        _mark(gamma)

    if knee:
        knee_sw_ok = blockers_ready and _ensure_feature_state(
            context, "KNEE", "QSL:45", "OSL:45:1", True
        )
        knee_mode_ok = blockers_ready and _ensure_dropdown_value(
            context, "KNEE MODE", "QSA:2D", "OSA:2D", "1"
        )
        if knee_sw_ok and knee_mode_ok:
            _apply_reset_commands(context, knee)
        else:
            _skip_reset_commands(
                context, knee,
                "could not verify KNEE and non-AUTO KNEE MODE"
            )
        _mark(knee)

    if white_clip:
        ok = blockers_ready and _ensure_feature_state(
            context, "WHITE CLIP", "QSA:2E", "OSA:2E:1", True
        )
        if ok:
            _apply_reset_commands(context, white_clip)
        else:
            _skip_reset_commands(context, white_clip, "WHITE CLIP could not be enabled")
        _mark(white_clip)

    if detail:
        ok = blockers_ready and _ensure_feature_state(
            context, "DETAIL", "QDT", "ODT:1", True
        )
        if ok:
            _apply_reset_commands(context, detail)
        else:
            _skip_reset_commands(
                context, detail,
                "DETAIL could not be enabled or global blockers (V-LOG/HDR) not cleared"
            )
        _mark(detail)

    for group, name in (
        (dnr,      "global blockers (V-LOG/HDR) could not be confirmed OFF"),
        (pedestal, "global blockers (V-LOG/HDR) could not be confirmed OFF"),
        (matrix,   "global blockers (V-LOG/HDR) could not be confirmed OFF"),
        (rgb_gain, "global blockers (V-LOG/HDR) could not be confirmed OFF"),
    ):
        if group:
            if blockers_ready:
                _apply_reset_commands(context, group)
            else:
                _skip_reset_commands(context, group, name)
            _mark(group)

    if flare:
        ok = prep["vlog_off"] and _ensure_feature_state(
            context, "FLARE", "QSA:11", "OSA:11:1", True
        )
        if ok:
            _apply_reset_commands(context, flare)
        else:
            _skip_reset_commands(
                context, flare,
                "FLARE could not be enabled or V-LOG could not be set OFF"
            )
        _mark(flare)

    if color_correct:
        ok = blockers_ready and _ensure_feature_state(
            context, "COLOR CORRECT", "QSA:85", "OSA:85:1", True
        )
        if ok:
            _apply_reset_commands(context, color_correct)
        else:
            _skip_reset_commands(
                context, color_correct,
                "COLOR CORRECT could not be verified ON or global blockers not cleared"
            )
        _mark(color_correct)

    remaining = [e for e in entries if e["index"] not in handled]
    _apply_reset_commands(context, remaining)


def run_reset(context) -> None:
    prep = _prepare_reset_environment(context)
    _run_reset_sequence(context, prep)
