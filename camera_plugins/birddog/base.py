"""
camera_plugins/birddog/base.py — Shared BirdDog REST helpers.

Used by all BirdDog camera modules in camera_plugins/birddog/.

API difference from camera_types/:
    context.send_command() returns str | None here (new ResetContext interface).

Command encoding for BirdDogTransport.send_command():
    GET:  build_get_cmd("/path")         → "GET /path"
    POST: build_post_cmd("/path", body)  → "POST /path {json_body}"

Typical usage in a camera module:

    from camera_plugins.birddog.base import (
        PROTOCOL,
        build_post_cmd,
        send_post,
        query_raw,
    )

    CAMERA_ID    = "P200A5"
    DISPLAY_NAME = "BirdDog P200"
    PROTOCOL     = PROTOCOL  # "birddog"

    def run_reset(context):
        send_post(context, "ColourMatrix", "/birddogcmsetup", _CM_DEFAULTS)
"""

from __future__ import annotations

import json
from typing import Any, Optional

PROTOCOL: str = "birddog"


def build_get_cmd(path: str) -> str:
    """Builds a GET command string for BirdDogTransport.send_command."""
    return f"GET {path}"


def build_post_cmd(path: str, body: dict) -> str:
    """Builds a POST command string for BirdDogTransport.send_command."""
    return f"POST {path} {json.dumps(body)}"


def query_raw(context: Any, path: str) -> Optional[str]:
    """
    Sends GET to path. Returns stripped response body or None on error.
    """
    body: Optional[str] = context.send_command(build_get_cmd(path))
    if body is None:
        context.logging.warning(f"Reset: GET {path} — no response")
        return None
    body = body.strip()
    if not body:
        context.logging.warning(f"Reset: GET {path} — empty response")
        return None
    return body


def send_post(context: Any, label: str, path: str, body: dict) -> bool:
    """
    Sends POST to path with JSON body. Returns True if a response was received.
    """
    cmd = build_post_cmd(path, body)
    response: Optional[str] = context.send_command(cmd)
    if response is None:
        context.logging.warning(f"Reset: '{label}' POST {path} — no response")
        return False
    context.record_success()
    return True
