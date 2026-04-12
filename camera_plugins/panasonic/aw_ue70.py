"""
camera_plugins/panasonic/aw_ue70.py — Panasonic AW-UE70 series

Same AW command set as HE40 series per Panasonic Interface Specifications v1.12 (2020).
Covers: AW-UE70, AW-UN70, AW-UE65, AW-UE63.
Only CAMERA_ID, CAMERA_ID_ALIASES, and DISPLAY_NAME differ from aw_he40.
"""

from camera_plugins.panasonic.aw_he40 import *  # noqa: F401,F403

CAMERA_ID         = "AW-UE70"
CAMERA_ID_ALIASES = ["AW-UN70", "AW-UE65", "AW-UE63"]
DISPLAY_NAME      = "Panasonic AW-UE70"
