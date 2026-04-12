import logging
from typing import Optional

import requests


def send_command(command: str, ip: str, port: str):
    """Send a CGI command to the camera. Returns the Response or None on failure."""
    url = f"http://{ip}:{port}/cgi-bin/aw_cam?{command}"
    logging.info(f"HTTP CMD: GET {url}")
    try:
        response = requests.get(url, timeout=3)
        response_text = (response.text or "").strip().replace("\r", "\\r").replace("\n", "\\n")
        logging.info(f"HTTP RESP: status={response.status_code} body={response_text}")
        return response
    except requests.exceptions.RequestException as exc:
        logging.error(f"HTTP RESP: exception={exc}")
        return None


def is_success_response(response) -> bool:
    """Return True if the camera responded with HTTP 200 and no error prefix."""
    if response is None:
        return False
    if response.status_code != 200:
        return False
    body = (response.text or "").strip()
    if body.startswith(("ER1:", "ER2:", "ER3:")):
        return False
    return True


def query_camera_id(ip: str, port: str) -> Optional[str]:
    """Send QID query and return the raw response text, or None on failure."""
    response = send_command("cmd=QID&res=1", ip, port)
    if response is None or response.status_code != 200:
        return None
    text = (response.text or "").strip()
    if not text or text.startswith(("ER1:", "ER2:", "ER3:")):
        return None
    return text
