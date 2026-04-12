"""
NDI video input layer — ctypes wrapper around NDI 6 SDK.

Provides:
    list_sources(timeout_ms)    -> list[str]
    grab_frame(ndi_name)        -> np.ndarray  shape (H, W, 3) RGB uint8
    NDIFrameStream(ndi_name)    -> context manager for continuous frame capture
    encode_jpeg(frame, width)   -> bytes  JPEG-encoded at reduced resolution
"""

import ctypes
import io
import os
import time

import numpy as np
from PIL import Image

# ---------------------------------------------------------------------------
# Load the NDI 6 runtime DLL — soft-fail if not found anywhere
# ---------------------------------------------------------------------------

_DLL_NAME = "Processing.NDI.Lib.x64.dll"

# Search order:
#   1. lib/ndi/ next to the project root  (bundled — no install needed)
#   2. NDI_RUNTIME_DIR_V6 env var         (SDK installer sets this)
#   3. Default SDK install path
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CANDIDATE_PATHS = [
    os.path.join(_PROJECT_ROOT, "lib", "ndi", _DLL_NAME),
    os.path.join(
        os.environ.get("NDI_RUNTIME_DIR_V6", r"C:\Program Files\NDI\NDI 6 SDK\Bin\x64"),
        _DLL_NAME,
    ),
]

_lib: "ctypes.CDLL | None" = None
_LOAD_ERROR: "str | None" = None

for _candidate in _CANDIDATE_PATHS:
    try:
        _lib = ctypes.CDLL(_candidate)
        break
    except OSError:
        continue

if _lib is None:
    _LOAD_ERROR = (
        f"NDI runtime DLL ({_DLL_NAME}) not found. "
        f"Place it in lib/ndi/ or install the NDI 6 SDK from ndi.video."
    )


def _require_sdk() -> None:
    """Raise a clear RuntimeError when the SDK is unavailable."""
    if _lib is None:
        raise RuntimeError(_LOAD_ERROR or "NDI SDK not available.")


# ---------------------------------------------------------------------------
# Struct definitions
# ---------------------------------------------------------------------------

class _NDIlib_source_t(ctypes.Structure):
    _fields_ = [
        ("p_ndi_name",   ctypes.c_char_p),
        ("p_url_address", ctypes.c_char_p),
    ]


class _NDIlib_find_create_t(ctypes.Structure):
    _fields_ = [
        ("show_local_sources", ctypes.c_bool),
        ("p_groups",           ctypes.c_char_p),
        ("p_extra_ips",        ctypes.c_char_p),
    ]


class _NDIlib_recv_create_v3_t(ctypes.Structure):
    _fields_ = [
        ("source_to_connect_to", _NDIlib_source_t),
        ("color_format",         ctypes.c_int),
        ("bandwidth",            ctypes.c_int),
        ("allow_video_fields",   ctypes.c_bool),
        ("p_ndi_recv_name",      ctypes.c_char_p),
    ]


class _NDIlib_video_frame_v2_t(ctypes.Structure):
    _fields_ = [
        ("xres",                 ctypes.c_int),
        ("yres",                 ctypes.c_int),
        ("FourCC",               ctypes.c_int),
        ("frame_rate_N",         ctypes.c_int),
        ("frame_rate_D",         ctypes.c_int),
        ("picture_aspect_ratio", ctypes.c_float),
        ("frame_format_type",    ctypes.c_int),
        ("timecode",             ctypes.c_int64),
        ("p_data",               ctypes.c_void_p),
        ("line_stride_in_bytes", ctypes.c_int),
        ("p_metadata",           ctypes.c_char_p),
        ("timestamp",            ctypes.c_int64),
    ]


# ---------------------------------------------------------------------------
# Enum / constant values
# ---------------------------------------------------------------------------

_NDIlib_recv_color_format_RGBX_RGBA = 2   # RGBX when no alpha (our case)
_NDIlib_recv_bandwidth_highest      = 100
_NDIlib_frame_type_video            = 1
_NDIlib_frame_type_none             = 0
_NDIlib_frame_type_error            = 4


# ---------------------------------------------------------------------------
# Function signatures
# ---------------------------------------------------------------------------

# NDIlib_initialize / NDIlib_destroy
_lib.NDIlib_initialize.restype  = ctypes.c_bool
_lib.NDIlib_initialize.argtypes = []
_lib.NDIlib_destroy.restype     = None
_lib.NDIlib_destroy.argtypes    = []

# Finder
_lib.NDIlib_find_create_v2.restype  = ctypes.c_void_p
_lib.NDIlib_find_create_v2.argtypes = [ctypes.POINTER(_NDIlib_find_create_t)]

_lib.NDIlib_find_destroy.restype  = None
_lib.NDIlib_find_destroy.argtypes = [ctypes.c_void_p]

_lib.NDIlib_find_wait_for_sources.restype  = ctypes.c_bool
_lib.NDIlib_find_wait_for_sources.argtypes = [ctypes.c_void_p, ctypes.c_uint32]

_lib.NDIlib_find_get_current_sources.restype  = ctypes.POINTER(_NDIlib_source_t)
_lib.NDIlib_find_get_current_sources.argtypes = [
    ctypes.c_void_p,
    ctypes.POINTER(ctypes.c_uint32),
]

# Receiver
_lib.NDIlib_recv_create_v3.restype  = ctypes.c_void_p
_lib.NDIlib_recv_create_v3.argtypes = [ctypes.POINTER(_NDIlib_recv_create_v3_t)]

_lib.NDIlib_recv_destroy.restype  = None
_lib.NDIlib_recv_destroy.argtypes = [ctypes.c_void_p]

_lib.NDIlib_recv_capture_v2.restype  = ctypes.c_int
_lib.NDIlib_recv_capture_v2.argtypes = [
    ctypes.c_void_p,                            # receiver instance
    ctypes.POINTER(_NDIlib_video_frame_v2_t),   # video frame out
    ctypes.c_void_p,                            # audio (NULL)
    ctypes.c_void_p,                            # metadata (NULL)
    ctypes.c_uint32,                            # timeout_in_ms
]

_lib.NDIlib_recv_free_video_v2.restype  = None
_lib.NDIlib_recv_free_video_v2.argtypes = [
    ctypes.c_void_p,
    ctypes.POINTER(_NDIlib_video_frame_v2_t),
]


# ---------------------------------------------------------------------------
# Initialise the NDI runtime once — only when SDK loaded successfully
# ---------------------------------------------------------------------------

if _lib is not None:
    if not _lib.NDIlib_initialize():
        _lib = None
        _LOAD_ERROR = "NDIlib_initialize() returned false — NDI runtime init failed."


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def is_available() -> bool:
    """Return True if the NDI 6 SDK is loaded and initialised."""
    return _lib is not None


def list_sources(timeout_ms: int = 3000) -> list[str]:
    """Return NDI source names visible on the network.

    Waits up to *timeout_ms* for discovery to settle before returning.
    Raises RuntimeError if the NDI SDK is not installed.
    """
    _require_sdk()
    create = _NDIlib_find_create_t(show_local_sources=True, p_groups=None, p_extra_ips=None)
    finder = _lib.NDIlib_find_create_v2(ctypes.byref(create))
    if not finder:
        raise RuntimeError("NDIlib_find_create_v2() returned NULL")

    try:
        _lib.NDIlib_find_wait_for_sources(finder, timeout_ms)
        count = ctypes.c_uint32(0)
        sources_ptr = _lib.NDIlib_find_get_current_sources(finder, ctypes.byref(count))
        return [
            sources_ptr[i].p_ndi_name.decode("utf-8")
            for i in range(count.value)
            if sources_ptr[i].p_ndi_name
        ]
    finally:
        _lib.NDIlib_find_destroy(finder)


def grab_frame(ndi_name: str, timeout_ms: int = 5000) -> np.ndarray:
    """Connect to an NDI source, grab one video frame, and disconnect.

    Returns an (H, W, 3) uint8 NumPy array in RGB order.
    Raises RuntimeError if the NDI SDK is not installed or no frame arrives.
    """
    _require_sdk()
    name_bytes = ndi_name.encode("utf-8")

    source = _NDIlib_source_t(p_ndi_name=name_bytes, p_url_address=None)
    create = _NDIlib_recv_create_v3_t(
        source_to_connect_to=source,
        color_format=_NDIlib_recv_color_format_RGBX_RGBA,
        bandwidth=_NDIlib_recv_bandwidth_highest,
        allow_video_fields=False,
        p_ndi_recv_name=b"smart-matching",
    )

    receiver = _lib.NDIlib_recv_create_v3(ctypes.byref(create))
    if not receiver:
        raise RuntimeError(f"NDIlib_recv_create_v3() returned NULL for source {ndi_name!r}")

    try:
        return _recv_one_frame(receiver, ndi_name, timeout_ms)
    finally:
        _lib.NDIlib_recv_destroy(receiver)


def _recv_one_frame(
    receiver: int,
    ndi_name: str,
    timeout_ms: int,
) -> np.ndarray:
    """Poll the receiver until a video frame arrives or timeout expires."""
    deadline = time.monotonic() + timeout_ms / 1000.0
    video_frame = _NDIlib_video_frame_v2_t()

    while time.monotonic() < deadline:
        remaining_ms = max(1, int((deadline - time.monotonic()) * 1000))
        frame_type = _lib.NDIlib_recv_capture_v2(
            receiver,
            ctypes.byref(video_frame),
            None,   # audio — not needed
            None,   # metadata — not needed
            remaining_ms,
        )

        if frame_type == _NDIlib_frame_type_error:
            raise RuntimeError(f"NDI recv error on source {ndi_name!r}")

        if frame_type == _NDIlib_frame_type_video:
            try:
                return _video_frame_to_rgb(video_frame)
            finally:
                _lib.NDIlib_recv_free_video_v2(receiver, ctypes.byref(video_frame))

    raise RuntimeError(
        f"No video frame received from {ndi_name!r} within {timeout_ms} ms"
    )


def _video_frame_to_rgb(vf: _NDIlib_video_frame_v2_t) -> np.ndarray:
    """Convert an NDI RGBX video frame to an (H, W, 3) RGB uint8 array."""
    w, h = vf.xres, vf.yres
    stride = vf.line_stride_in_bytes or (w * 4)  # RGBX = 4 bytes/pixel

    buf = (ctypes.c_uint8 * (stride * h)).from_address(vf.p_data)
    arr = np.frombuffer(buf, dtype=np.uint8).reshape((h, stride // 4, 4))
    # Drop the X (padding) channel, keep R G B
    return arr[:, :w, :3].copy()


# ---------------------------------------------------------------------------
# Continuous streaming
# ---------------------------------------------------------------------------

class NDIFrameStream:
    """Persistent NDI receiver — keeps the connection open for repeated grabs.

    Use as a context manager::

        with NDIFrameStream("MS-LAPI (Test Pattern)") as stream:
            frame = stream.next_frame()   # np.ndarray (H, W, 3) RGB or None
    """

    def __init__(self, ndi_name: str):
        self._ndi_name = ndi_name
        self._name_bytes = ndi_name.encode("utf-8")
        self._receiver = None

    def open(self):
        _require_sdk()
        source = _NDIlib_source_t(p_ndi_name=self._name_bytes, p_url_address=None)
        create = _NDIlib_recv_create_v3_t(
            source_to_connect_to=source,
            color_format=_NDIlib_recv_color_format_RGBX_RGBA,
            bandwidth=_NDIlib_recv_bandwidth_highest,
            allow_video_fields=False,
            p_ndi_recv_name=b"smart-matching-monitor",
        )
        self._receiver = _lib.NDIlib_recv_create_v3(ctypes.byref(create))
        if not self._receiver:
            raise RuntimeError(
                f"NDIlib_recv_create_v3() returned NULL for source {self._ndi_name!r}"
            )

    def close(self):
        if self._receiver:
            _lib.NDIlib_recv_destroy(self._receiver)
            self._receiver = None

    def next_frame(self, timeout_ms: int = 200) -> "np.ndarray | None":
        """Return the next video frame, or None if nothing arrived within timeout."""
        if not self._receiver:
            raise RuntimeError("NDIFrameStream is not open")

        video_frame = _NDIlib_video_frame_v2_t()
        frame_type = _lib.NDIlib_recv_capture_v2(
            self._receiver,
            ctypes.byref(video_frame),
            None,
            None,
            timeout_ms,
        )

        if frame_type == _NDIlib_frame_type_error:
            raise RuntimeError(f"NDI recv error on source {self._ndi_name!r}")

        if frame_type == _NDIlib_frame_type_video:
            try:
                return _video_frame_to_rgb(video_frame)
            finally:
                _lib.NDIlib_recv_free_video_v2(self._receiver, ctypes.byref(video_frame))

        return None  # timeout or other frame type

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, *_):
        self.close()


# ---------------------------------------------------------------------------
# JPEG encoding helper
# ---------------------------------------------------------------------------

def encode_jpeg(frame: np.ndarray, width: int = 640, quality: int = 70) -> bytes:
    """Resize *frame* to *width* px wide (preserving aspect) and JPEG-encode it."""
    h, w = frame.shape[:2]
    new_h = max(1, int(h * width / w))
    img = Image.fromarray(frame)
    img = img.resize((width, new_h), Image.BILINEAR)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality)
    return buf.getvalue()
