"""
camera_plugins/panasonic/aw_ue145.py — Panasonic AW-UE145

Same reset logic as AW-UE150A. Only CAMERA_ID, CAMERA_ID_ALIASES,
and DISPLAY_NAME differ.
"""

from camera_plugins.panasonic.aw_ue150 import *  # noqa: F401,F403

CAMERA_ID         = "AW-UE145"
CAMERA_ID_ALIASES = ["AW-UE150HE", "AW-UE150HE145"]
DISPLAY_NAME      = "Panasonic AW-UE145"
