"""
camera_plugins/panasonic/aw_he60.py — Panasonic AW-HE60 series

Same command set as AW-HE50 series per Panasonic Interface Specifications v1.12 (2020).
Covers: AW-HE60, AW-HE60H, AW-HE60E, AW-HE60S.
Only CAMERA_ID, CAMERA_ID_ALIASES, and DISPLAY_NAME differ from aw_he50.
"""

from camera_plugins.panasonic.aw_he50 import *  # noqa: F401,F403

CAMERA_ID         = "AW-HE60"
CAMERA_ID_ALIASES = ["AW-HE60H", "AW-HE60E", "AW-HE60S"]
DISPLAY_NAME      = "Panasonic AW-HE60"
