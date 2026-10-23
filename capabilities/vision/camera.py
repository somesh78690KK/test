"""T.A.R.O. - Camera capability (TASK-064).

ARCHITECTURE reference: section 10 (Vision Pipeline).
RULES reference: section 3, 10.
TASKS: TASK-064.

Camera preview uses OpenCV as fallback for single-frame capture and analysis.
Camera is OFF by default. Must be explicitly enabled.
"""

from __future__ import annotations

import io
import time
from typing import Any

from core.log.setup import get_logger
from core.tools.base import BaseTool, RiskLevel, ToolCategory, ToolResult

logger = get_logger(__name__)

# Camera state
_camera_enabled = False


class CameraTool(BaseTool):
    """Captures a single frame from the webcam for analysis.

    Acceptance (TASK-064): Camera off by default; analysis works on fallback path.
    """

    name = "camera.capture"
    description = (
        "Capture a single frame from the webcam. Camera must be explicitly enabled. "
        "Returns frame dimensions and size. Use screen.describe to analyze the frame."
    )
    category = ToolCategory.VISION
    risk = RiskLevel.MEDIUM  # Camera access requires confirmation
    timeout_s = 10
    parameters = {
        "type": "object",
        "properties": {
            "enable": {
                "type": "boolean",
                "description": "Set to true to enable camera access for this session.",
            },
            "camera_index": {
                "type": "integer",
                "description": "Camera device index (default 0).",
            },
        },
    }

    last_frame: bytes | None = None
    last_frame_dims: tuple[int, int] = (0, 0)

    async def run(self, args: dict) -> ToolResult:
        return await self.execute(**args)

    async def execute(self, **kwargs: Any) -> ToolResult:
        global _camera_enabled

        enable = kwargs.get("enable", False)
        camera_index = kwargs.get("camera_index", 0)

        if enable:
            _camera_enabled = True
            logger.info("camera_enabled")
            return ToolResult.ok("Camera access enabled for this session.")

        if not _camera_enabled:
            return ToolResult.error_result(
                "Camera is disabled by default. Call with enable=true to activate."
            )

        start = time.monotonic()

        try:
            import cv2
            from PIL import Image

            cap = cv2.VideoCapture(camera_index)
            if not cap.isOpened():
                return ToolResult.error_result(
                    f"Cannot open camera device {camera_index}. "
                    "Check if the camera is connected and not in use."
                )

            try:
                ret, frame = cap.read()
                if not ret or frame is None:
                    return ToolResult.error_result("Failed to read frame from camera.")

                # Convert BGR (OpenCV) to RGB (PIL)
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                img = Image.fromarray(frame_rgb)

                # Downscale
                from capabilities.vision.capture import CAPTURE_WIDTH, CAPTURE_HEIGHT, JPEG_QUALITY

                img.thumbnail((CAPTURE_WIDTH, CAPTURE_HEIGHT), Image.LANCZOS)
                w, h = img.size

                # Encode JPEG
                buf = io.BytesIO()
                img.save(buf, format="JPEG", quality=JPEG_QUALITY)
                jpeg_bytes = buf.getvalue()

                self.last_frame = jpeg_bytes
                self.last_frame_dims = (w, h)

                # Also make it available to the screen capture tool's frame slot
                from capabilities.vision.capture import _screen_capture_tool

                _screen_capture_tool.last_frame = jpeg_bytes
                _screen_capture_tool.last_frame_dims = (w, h)

                elapsed = (time.monotonic() - start) * 1000
                size_kb = len(jpeg_bytes) / 1024

                logger.info(
                    "camera_frame_captured",
                    width=w,
                    height=h,
                    size_kb=round(size_kb, 1),
                    elapsed_ms=round(elapsed, 1),
                )
                return ToolResult.ok(
                    f"Camera frame captured: {w}x{h}, {size_kb:.1f} KB. "
                    f"Use screen.describe or screen.ocr to analyze.",
                    duration_ms=int(elapsed),
                    width=w,
                    height=h,
                )
            finally:
                cap.release()

        except ImportError:
            return ToolResult.error_result(
                "opencv-python-headless is required for camera capture. "
                "Install with: pip install opencv-python-headless"
            )
        except Exception as e:
            logger.error("camera_capture_error", error=str(e))
            return ToolResult.error_result(f"Camera capture failed: {e}")


CAMERA_TOOLS: list[BaseTool] = [CameraTool()]
