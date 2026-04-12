"""
camera_plugins/panasonic/aw_he40.py — Panasonic AW-HE40 series

Compact HD/4K PTZ cameras sharing the HE40 AW command set.
Covers: AW-HE40, AW-HE65, AW-HE70, AW-HE48, AW-HE58, AW-HE35, AW-HE38,
        AW-HN38/40/65/70.
Alias modules aw_he42.py (HE42 series) and aw_ue70.py (UE70 series) derive
from this module — they share the same image-quality command set.
Commands from Panasonic HD/4K Integrated Camera Interface Specifications v1.12 (2020).
Helper functions come from camera_plugins/panasonic/base.py.
"""

from camera_plugins.panasonic.base import (
    PROTOCOL,
    apply_reset_commands as _apply_reset_commands,
    build_entries as _build_entries,
    ensure_dropdown_value as _ensure_dropdown_value,
    extract_value as _extract_value,
    filter_entries as _filter_entries,
    query_raw as _query_raw,
    send_set_command as _send_set_command,
    skip_reset_commands as _skip_reset_commands,
)

CAMERA_ID         = "AW-HE40"
CAMERA_ID_ALIASES = [
    "AW-HE40S", "AW-HE40W", "AW-HE40HE",
    "AW-HE65", "AW-HE65H", "AW-HE65E",
    "AW-HE70", "AW-HE70HE",
    "AW-HE48", "AW-HE58",
    "AW-HE35", "AW-HE38",
    "AW-HN38", "AW-HN40", "AW-HN65", "AW-HN70",
]
DISPLAY_NAME = "Panasonic AW-HE40"

# ---------------------------------------------------------------------------
# RESET_COMMANDS
# ---------------------------------------------------------------------------

RESET_COMMANDS = [
    # White balance ATW targets
    ("ATW TARGET R",                     "OSJ", "0D", "80"),
    ("ATW TARGET B",                     "OSJ", "0E", "80"),
    ("ATW SPEED",                        "OSI", "25", "0"),
    # Gamma — OSJ:D7: 0=HD, 1=Normal, 2=Cinema1, 3=Cinema2, 4=StillLike
    ("GAMMA",                            "OSA", "6A", "76"),
    # Matrix
    ("MATRIX TYPE",                      "OSE", "31", "0"),
    ("ADAPTIVE MATRIX",                  "OSJ", "4F", "0"),
    # DRS
    ("DRS",                              "OSE", "33", "0"),
    # Chroma
    ("CHROMA LEVEL",                     "OSD", "B0", "80"),
    ("CHROMA PHASE",                     "OSJ", "0B", "80"),
    # Knee
    ("KNEE MODE",                        "OSA", "2D", "1"),
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
    "auto_focus": {"on": "OAF:1",    "off": "OAF:0"},
    "auto_iris":  {"on": "ORS:1",    "off": "ORS:0"},
    "awb_black":  {"cmd": "OAS"},
    "aww_white":  {"cmd": "OWS"},
    "drs":        {"on": "OSE:33:1", "off": "OSE:33:0"},
    "white_clip": {"on": "OSA:2E:1", "off": "OSA:2E:0"},
    # Day/Night mode (IR cut filter)
    "night_mode": {"on": "OSI:1A:1", "off": "OSI:1A:0"},
}

UI_BUTTON_LABELS = {
    "auto_focus": "Auto Focus",
    "auto_iris":  "Auto Iris",
    "drs":        "DRS",
    "white_clip": "White Clip",
    "awb_black":  "ABB (Black)",
    "aww_white":  "AWW (White)",
    "night_mode": "Night Mode",
}

UI_LAYOUT = [
    ("drs",        "auto_iris",  "auto_focus", "color_temp"),
    ("white_clip", "night_mode", "awb_black",  "gamma"),
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
        ("Gamma is HD",         "OSJ:D7:00"),
        ("Gamma is Normal",     "OSJ:D7:01"),
        ("Gamma is Cinema 1",   "OSJ:D7:02"),
        ("Gamma is Cinema 2",   "OSJ:D7:03"),
        ("Gamma is Still Like", "OSJ:D7:04"),
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
    "night_mode": "QSI:1A",
}

UI_DROPDOWN_QUERIES = {
    "color_temp": "QAW",
    "gamma":      "QSJ:D7",
}

POST_RESET_FEATURE_STATES = [
    ("auto_iris",  True),
    ("auto_focus", False),
    ("drs",        False),
    ("white_clip", False),
    ("night_mode", False),
]

POST_RESET_DROPDOWN_DEFAULTS = {
    "color_temp": "White Balance is ATW",
}

POST_RESET_STATUS_QUERIES = [
    ("Auto Iris",  "QRS"),
    ("Auto Focus", "QAF"),
    ("DRS",        "QSE:33"),
    ("White Clip", "QSA:2E"),
    ("Night Mode", "QSI:1A"),
    ("White Balance Mode", "QAW"),
    ("Gamma Mode", "QSJ:D7"),
]

# ---------------------------------------------------------------------------
# Command key sets
# ---------------------------------------------------------------------------

_ATW_KEYS = {("OSJ", "0D"), ("OSJ", "0E")}

_KNEE_KEYS = {("OSA", "2D")}

_COLOR_CORRECT_KEYS = {
    ("OSD", "80"), ("OSD", "81"), ("OSD", "82"), ("OSD", "83"),
    ("OSD", "84"), ("OSD", "85"), ("OSD", "86"), ("OSD", "87"),
    ("OSD", "88"), ("OSD", "89"), ("OSD", "8A"), ("OSD", "8B"),
    ("OSD", "8C"), ("OSD", "8D"), ("OSD", "8E"), ("OSD", "8F"),
    ("OSD", "90"), ("OSD", "91"), ("OSD", "92"), ("OSD", "93"),
    ("OSD", "94"), ("OSD", "95"), ("OSD", "96"), ("OSD", "97"),
}

_CONDITIONAL_KEYS = {("OSA", "6A"), ("OSE", "33")}

# ---------------------------------------------------------------------------
# Reset logic — mirrors aw_ue80.py pattern (scene-file + gamma prerequisite)
# ---------------------------------------------------------------------------

def _prepare_reset_environment(context) -> dict:
    prep = {
        "scene_not_full_auto": False,
        "gamma_mode_normal":   False,
        "drs_off":             False,
    }

    scene_value = _extract_value(_query_raw(context, "QSF"))
    if scene_value == "4":
        context.logging.info("Reset prep: setting SCENE FILE to Scene1 (not Full Auto)")
        if _send_set_command(context, "SCENE FILE", "XSF:1"):
            verify_scene = _extract_value(_query_raw(context, "QSF"))
            prep["scene_not_full_auto"] = verify_scene != "4" and verify_scene is not None
        else:
            prep["scene_not_full_auto"] = False
    else:
        prep["scene_not_full_auto"] = scene_value is not None

    if prep["scene_not_full_auto"]:
        context.logging.info("Reset prep: setting GAMMA MODE to Normal")
        prep["gamma_mode_normal"] = _ensure_dropdown_value(
            context, "GAMMA MODE", "QSJ:D7", "OSJ:D7", "01"
        )

    if prep["scene_not_full_auto"] and prep["gamma_mode_normal"]:
        context.logging.info("Reset prep: setting DRS OFF")
        prep["drs_off"] = _ensure_dropdown_value(
            context, "DRS", "QSE:33", "OSE:33", "0"
        )

    return prep


def _run_reset_sequence(context, prep: dict) -> None:
    entries = _build_entries(RESET_COMMANDS)

    atw           = _filter_entries(entries, _ATW_KEYS)
    knee          = _filter_entries(entries, _KNEE_KEYS)
    color_correct = _filter_entries(entries, _COLOR_CORRECT_KEYS)

    handled: set[int] = set()

    def _mark(*groups):
        for g in groups:
            for e in g:
                handled.add(e["index"])

    if atw:
        atw_ready = _ensure_dropdown_value(
            context, "WHITE BALANCE MODE", "QAW", "OAW", "0"
        )
        if atw_ready:
            _apply_reset_commands(context, atw)
        else:
            _skip_reset_commands(context, atw, "WHITE BALANCE MODE could not be set to ATW")
        _mark(atw)

    if color_correct:
        matrix_ready = _ensure_dropdown_value(
            context, "MATRIX TYPE", "QSE:31", "OSE:31", "3"
        )
        if matrix_ready:
            _apply_reset_commands(context, color_correct)
            _send_set_command(context, "MATRIX TYPE", "OSE:31:0")
        else:
            _skip_reset_commands(context, color_correct, "MATRIX TYPE could not be set to USER")
        _mark(color_correct)

    if knee:
        knee_ready = (
            prep.get("scene_not_full_auto")
            and prep.get("gamma_mode_normal")
            and prep.get("drs_off")
        )
        knee_query = _query_raw(context, "QSA:2D") if knee_ready else None
        if knee_query is not None:
            for entry in knee:
                ok = _send_set_command(
                    context,
                    entry["label"],
                    f"{entry['cmd']}:{entry['addr']}:{entry['data']}",
                )
                if not ok:
                    context.logging.warning(
                        f"Skipping {entry['label']}: write not accepted in current mode"
                    )
        else:
            _skip_reset_commands(
                context, knee,
                "KNEE MODE prerequisites not met (Scene/Gamma Mode/DRS) or query unavailable",
            )
        _mark(knee)

    remaining = [e for e in entries if e["index"] not in handled]
    conditional = _filter_entries(remaining, _CONDITIONAL_KEYS)
    default     = [e for e in remaining if e not in conditional]

    conditional_ready = prep.get("scene_not_full_auto") and prep.get("gamma_mode_normal")
    if conditional_ready:
        for entry in conditional:
            ok = _send_set_command(
                context,
                entry["label"],
                f"{entry['cmd']}:{entry['addr']}:{entry['data']}",
            )
            if not ok:
                context.logging.warning(
                    f"Skipping {entry['label']}: write not accepted in current mode"
                )
    else:
        _skip_reset_commands(
            context, conditional,
            "GAMMA/DRS prerequisites not met (Scene/Gamma Mode)",
        )

    _apply_reset_commands(context, default)


def run_reset(context) -> None:
    prep = _prepare_reset_environment(context)
    _run_reset_sequence(context, prep)
