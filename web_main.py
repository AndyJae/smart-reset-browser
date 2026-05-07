"""Entry point: starts uvicorn and opens the browser."""

import ctypes
import os
import sys
import threading
import time
import webbrowser

import pystray
import uvicorn
from PIL import Image

# Import the app object directly so PyInstaller can resolve it without
# performing a runtime string-based import inside a frozen bundle.
from web.app import app  # noqa: E402

_MUTEX_NAME = "Global\\SmartResetApp_SingleInstance"


def _ensure_single_instance():
    """Create a named mutex. If it already exists, show a message and exit.

    The mutex is a Windows kernel object held by the OS until the process
    exits — no need to keep a Python reference to the handle.
    """
    ctypes.windll.kernel32.CreateMutexW(None, True, _MUTEX_NAME)
    if ctypes.windll.kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
        ctypes.windll.user32.MessageBoxW(
            None,
            "Smart Reset is already running.\nCheck the system tray.",
            "Already Running",
            0x40 | 0x1000,  # MB_ICONINFORMATION | MB_SYSTEMMODAL
        )
        sys.exit(0)


_ensure_single_instance()

HOST = "127.0.0.1"
PORT = 8765
URL = f"http://{HOST}:{PORT}"


def _load_tray_image() -> Image.Image:
    """Return the logo image for the system tray icon."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return Image.open(os.path.join(base, "icon.ico"))


def _open_browser():
    """Wait briefly for the server to be ready, then open the browser."""
    time.sleep(1.2)
    webbrowser.open(URL)


def main():
    # When running as a windowless exe, sys.stdout/stderr are None.
    # Redirect to a log file so crashes are visible instead of silently swallowed.
    if sys.stdout is None or sys.stderr is None:
        _log_dir = os.path.dirname(sys.executable if getattr(sys, "frozen", False)
                                   else os.path.abspath(__file__))
        _log = open(os.path.join(_log_dir, "smart_reset.log"), "a", buffering=1)
        if sys.stdout is None:
            sys.stdout = _log
        if sys.stderr is None:
            sys.stderr = _log

    server = uvicorn.Server(uvicorn.Config(
        app,
        host=HOST,
        port=PORT,
        log_level="warning",
        reload=False,
    ))

    # Run uvicorn and browser opener in background threads.
    # The main thread is reserved for the system tray icon (Windows requirement).
    threading.Thread(target=server.run, daemon=True).start()
    threading.Thread(target=_open_browser, daemon=True).start()

    def on_open(_icon, _item):
        webbrowser.open(URL)

    def on_quit(icon, _item):
        server.should_exit = True
        icon.stop()
        os._exit(0)

    try:
        tray = pystray.Icon(
            "smart-reset",
            _load_tray_image(),
            "smart-reset",
            menu=pystray.Menu(
                pystray.MenuItem("Open", on_open, default=True),
                pystray.MenuItem("Quit", on_quit),
            ),
        )
        tray.run()  # blocks until on_quit calls icon.stop()
    except Exception as exc:
        ctypes.windll.user32.MessageBoxW(
            None,
            f"Smart Reset failed to create the system tray icon:\n\n{exc}\n\n"
            "The server is still running. Open http://127.0.0.1:8765 manually.",
            "Smart Reset — Tray Error",
            0x10 | 0x1000,  # MB_ICONERROR | MB_SYSTEMMODAL
        )
    finally:
        # Force-exit so the process terminates immediately and releases the
        # single-instance mutex. Without this, pystray's Windows backend or
        # uvicorn's graceful-shutdown thread can keep the process alive after
        # the tray loop ends, causing "already running" on the next launch.
        os._exit(0)


if __name__ == "__main__":
    main()
