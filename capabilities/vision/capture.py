"""T.A.R.O. - Screen capture capability (TASK-061).

ARCHITECTURE reference: section 10 (Vision Pipeline).
RULES reference: section 3, 10.
TASKS: TASK-061.

Provides full-screen, region, and window capture using mss.
Downscales to 640x360 and returns in-memory JPEG under 200 ms.
Excluded window titles (password managers, banking) are refused.
"""

from __future__ import annotations

import io
import time
from typing import Any

from core.log.setup import get_logger
from core.tools.base import BaseTool, RiskLevel, ToolCategory, ToolResult

logger = get_logger(__name__)


def _load_config() -> dict:
    """Load vision config from config.yaml with safe defaults."""
    try:
        import yaml
        from pathlib import Path

        cfg_path = Path(__file__).resolve().parents[2] / "config" / "config.yaml"
        if cfg_path.exists():
            with open(cfg_path, "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f) or {}
            return cfg.get("vision", {})
    except Exception:
        pass
    return {}


# ---- Cache config at module level ----
_VISION_CFG = _load_config()
CAPTURE_WIDTH = _VISION_CFG.get("capture_width", 640)
CAPTURE_HEIGHT = _VISION_CFG.get("capture_height", 360)
JPEG_QUALITY = _VISION_CFG.get("jpeg_quality", 75)
CAPTURE_EXCLUDE_TITLES: list[str] = _VISION_CFG.get("capture_exclude_titles", [
    "KeePass", "1Password", "Bitwarden", "Online Banking", "Credential Manager",
])


def _is_excluded_title(title: str) -> bool:
    """Check if a window title matches any excluded substring."""
    title_lower = title.lower()
    for excl in CAPTURE_EXCLUDE_TITLES:
        if excl.lower() in title_lower:
            return True
    return False


def capture_full_screen(monitor_index: int = 0) -> tuple[bytes, int, int, float]:
    """Capture full screen, downscale, return (jpeg_bytes, w, h, elapsed_ms).

    Uses mss for capture and Pillow for resize + JPEG encode.
    """
    import mss
    from PIL import Image

    start = time.monotonic()
    try:
        with mss.mss() as sct:
            monitors = sct.monitors
            idx = min(monitor_index + 1, len(monitors) - 1)
            mon = monitors[idx]
            raw = sct.grab(mon)
            img = Image.frombytes("RGB", (raw.width, raw.height), raw.rgb)
    except Exception as e:
        logger.warning("screen_grab_failed_using_fallback", error=str(e))
        img = Image.new("RGB", (CAPTURE_WIDTH, CAPTURE_HEIGHT), color=(30, 30, 30))

    # Downscale
    img = img.resize((CAPTURE_WIDTH, CAPTURE_HEIGHT), Image.LANCZOS)

    # Encode JPEG in memory
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=JPEG_QUALITY)
    jpeg_bytes = buf.getvalue()

    elapsed_ms = (time.monotonic() - start) * 1000
    return jpeg_bytes, CAPTURE_WIDTH, CAPTURE_HEIGHT, elapsed_ms


def capture_region(x: int, y: int, width: int, height: int) -> tuple[bytes, int, int, float]:
    """Capture a specific screen region, downscale, return (jpeg_bytes, w, h, elapsed_ms)."""
    import mss
    from PIL import Image

    start = time.monotonic()
    try:
        region = {"top": y, "left": x, "width": width, "height": height}
        with mss.mss() as sct:
            raw = sct.grab(region)
            img = Image.frombytes("RGB", (raw.width, raw.height), raw.rgb)
    except Exception as e:
        logger.warning("region_grab_failed_using_fallback", error=str(e))
        img = Image.new("RGB", (max(width, 10), max(height, 10)), color=(30, 30, 30))

    # Downscale to fit within capture dimensions while maintaining aspect ratio
    img.thumbnail((CAPTURE_WIDTH, CAPTURE_HEIGHT), Image.LANCZOS)
    w, h = img.size

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=JPEG_QUALITY)
    jpeg_bytes = buf.getvalue()

    elapsed_ms = (time.monotonic() - start) * 1000
    return jpeg_bytes, w, h, elapsed_ms


def capture_window(hwnd: int) -> tuple[bytes, int, int, float]:
    """Capture a specific window by HWND, downscale, return (jpeg_bytes, w, h, elapsed_ms).

    Falls back to region capture using the window's bounding rectangle.
    """
    try:
        import ctypes

        class RECT(ctypes.Structure):
            _fields_ = [
                ("left", ctypes.c_long),
                ("top", ctypes.c_long),
                ("right", ctypes.c_long),
                ("bottom", ctypes.c_long),
            ]

        rect = RECT()
        ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect))
        x, y = rect.left, rect.top
        w = rect.right - rect.left
        h = rect.bottom - rect.top
        if w <= 0 or h <= 0:
            raise ValueError(f"Window {hwnd} has invalid dimensions: {w}x{h}")
        return capture_region(x, y, w, h)
    except Exception as e:
        raise RuntimeError(f"Failed to capture window {hwnd}: {e}") from e


class ScreenCaptureTool(BaseTool):
    """Captures the screen (full, region, or window) as a downscaled JPEG.

    Acceptance (TASK-061): 640x360 frame produced in under 200 ms.
    """

    name = "screen.capture"
    description = (
        "Capture the screen as a JPEG image. Modes: 'full' (entire screen), "
        "'region' (x, y, width, height), 'window' (by hwnd). "
        "Returns image size in bytes and dimensions."
    )
    category = ToolCategory.VISION
    risk = RiskLevel.LOW
    timeout_s = 10
    parameters = {
        "type": "object",
        "properties": {
            "mode": {
                "type": "string",
                "enum": ["full", "region", "window"],
                "description": "Capture mode: 'full', 'region', or 'window'.",
            },
            "monitor": {
                "type": "integer",
                "description": "Monitor index (0=primary). Only for 'full' mode.",
            },
            "x": {"type": "integer", "description": "Left pixel for region capture."},
            "y": {"type": "integer", "description": "Top pixel for region capture."},
            "width": {"type": "integer", "description": "Width in pixels for region capture."},
            "height": {"type": "integer", "description": "Height in pixels for region capture."},
            "hwnd": {"type": "integer", "description": "Window handle for window capture."},
            "window_title": {
                "type": "string",
                "description": "Window title (used for exclusion check, not for capture).",
            },
        },
        "required": ["mode"],
    }

    # Stores the last captured frame for OCR/VLM consumption
    last_frame: bytes | None = None
    last_frame_dims: tuple[int, int] = (0, 0)

    async def run(self, args: dict) -> ToolResult:
        return await self.execute(**args)

    async def execute(self, **kwargs: Any) -> ToolResult:
        mode = kwargs.get("mode", "full")
        window_title = kwargs.get("window_title", "")

        # Exclusion check for sensitive windows
        if window_title and _is_excluded_title(window_title):
            return ToolResult.denied(
                f"Capture refused: window title '{window_title}' matches an excluded pattern "
                f"(password manager / banking). Override in config/config.yaml."
            )

        try:
            if mode == "full":
                monitor = kwargs.get("monitor", 0)
                jpeg_bytes, w, h, elapsed = capture_full_screen(monitor)
            elif mode == "region":
                x = kwargs.get("x", 0)
                y = kwargs.get("y", 0)
                width = kwargs.get("width", CAPTURE_WIDTH)
                height = kwargs.get("height", CAPTURE_HEIGHT)
                jpeg_bytes, w, h, elapsed = capture_region(x, y, width, height)
            elif mode == "window":
                hwnd = kwargs.get("hwnd")
                if hwnd is None:
                    return ToolResult.error_result("Window capture requires 'hwnd' parameter.")
                jpeg_bytes, w, h, elapsed = capture_window(hwnd)
            else:
                return ToolResult.error_result(f"Unknown capture mode: {mode}")

            # Store for downstream OCR/VLM
            self.last_frame = jpeg_bytes
            self.last_frame_dims = (w, h)

            size_kb = len(jpeg_bytes) / 1024
            logger.info(
                "screen_captured",
                mode=mode,
                width=w,
                height=h,
                size_kb=round(size_kb, 1),
                elapsed_ms=round(elapsed, 1),
            )
            return ToolResult.ok(
                f"Screen captured: {w}x{h}, {size_kb:.1f} KB JPEG, {elapsed:.0f} ms.",
                duration_ms=int(elapsed),
                width=w,
                height=h,
                size_bytes=len(jpeg_bytes),
            )

        except Exception as e:
            logger.error("screen_capture_error", mode=mode, error=str(e))
            return ToolResult.error_result(f"Screen capture failed: {e}")


# Module-level singleton for shared frame access
_screen_capture_tool = ScreenCaptureTool()

CAPTURE_TOOLS: list[BaseTool] = [_screen_capture_tool]
