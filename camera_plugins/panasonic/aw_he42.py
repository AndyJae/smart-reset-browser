"""
camera_plugins/panasonic/aw_he42.py — Panasonic AW-HE42 series

Same AW command set as HE40 series per Panasonic Interface Specifications v1.12 (2020).
Covers: AW-HE42, AW-HE75, AW-HE68.
Only CAMERA_ID, CAMERA_ID_ALIASES, and DISPLAY_NAME differ from aw_he40.
"""

from camera_plugins.panasonic.aw_he40 import *  # noqa: F401,F403

CAMERA_ID         = "AW-HE42"
CAMERA_ID_ALIASES = ["AW-HE75", "AW-HE68", "AW-HE42HE"]
DISPLAY_NAME      = "Panasonic AW-HE42"
