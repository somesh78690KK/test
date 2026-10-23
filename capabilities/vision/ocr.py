"""T.A.R.O. - OCR capability (TASK-062).

ARCHITECTURE reference: section 10 (Vision Pipeline).
RULES reference: section 3, 10.
TASKS: TASK-062.

Uses pytesseract for offline OCR on screen captures or image files.
Falls back gracefully if Tesseract is not installed.
"""

from __future__ import annotations

import io
import time
from pathlib import Path
from typing import Any

from core.log.setup import get_logger
from core.tools.base import BaseTool, RiskLevel, ToolCategory, ToolResult

logger = get_logger(__name__)

# Tesseract availability flag
_TESSERACT_AVAILABLE: bool | None = None


def _check_tesseract() -> bool:
    """Check if Tesseract OCR is installed and accessible."""
    global _TESSERACT_AVAILABLE
    if _TESSERACT_AVAILABLE is not None:
        return _TESSERACT_AVAILABLE
    try:
        import pytesseract

        # Try common Windows install paths
        import shutil

        if shutil.which("tesseract") is None:
            common_paths = [
                r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
            ]
            for p in common_paths:
                if Path(p).exists():
                    pytesseract.pytesseract.tesseract_cmd = p
                    break

        version = pytesseract.get_tesseract_version()
        logger.info("tesseract_found", version=str(version))
        _TESSERACT_AVAILABLE = True
    except Exception as e:
        logger.warning("tesseract_not_found", error=str(e))
        _TESSERACT_AVAILABLE = False
    return _TESSERACT_AVAILABLE


def ocr_from_bytes(jpeg_bytes: bytes) -> str:
    """Run OCR on raw image bytes. Returns extracted text."""
    import pytesseract
    from PIL import Image

    img = Image.open(io.BytesIO(jpeg_bytes))
    text = pytesseract.image_to_string(img, lang="eng")
    return text.strip()


def ocr_from_file(image_path: str) -> str:
    """Run OCR on an image file. Returns extracted text."""
    import pytesseract
    from PIL import Image

    img = Image.open(image_path)
    text = pytesseract.image_to_string(img, lang="eng")
    return text.strip()


class OCRTool(BaseTool):
    """Extracts text from screen captures or image files using Tesseract OCR.

    Acceptance (TASK-062): Known test image OCR matches expected text.
    """

    name = "screen.ocr"
    description = (
        "Extract text from the current screen capture or an image file using OCR. "
        "If no image_path is given, uses the last screen capture frame."
    )
    category = ToolCategory.VISION
    risk = RiskLevel.SAFE
    timeout_s = 15
    parameters = {
        "type": "object",
        "properties": {
            "image_path": {
                "type": "string",
                "description": "Path to an image file. If omitted, uses the last screen capture.",
            },
        },
    }

    async def run(self, args: dict) -> ToolResult:
        return await self.execute(**args)

    async def execute(self, **kwargs: Any) -> ToolResult:
        if not _check_tesseract():
            return ToolResult.error_result(
                "Tesseract OCR is not installed. Install from "
                "https://github.com/UB-Mannheim/tesseract/wiki and add to PATH."
            )

        image_path = kwargs.get("image_path")
        start = time.monotonic()

        try:
            if image_path:
                p = Path(image_path)
                if not p.exists():
                    return ToolResult.error_result(f"Image file not found: {image_path}")
                text = ocr_from_file(image_path)
            else:
                # Use last captured frame from screen capture tool
                from capabilities.vision.capture import _screen_capture_tool

                if _screen_capture_tool.last_frame is None:
                    return ToolResult.error_result(
                        "No screen capture available. Run screen.capture first."
                    )
                text = ocr_from_bytes(_screen_capture_tool.last_frame)

            elapsed = (time.monotonic() - start) * 1000

            if not text:
                return ToolResult.ok(
                    "[No text detected in image]",
                    duration_ms=int(elapsed),
                )

            logger.info("ocr_complete", chars=len(text), elapsed_ms=round(elapsed, 1))
            return ToolResult.ok(
                text,
                duration_ms=int(elapsed),
                char_count=len(text),
            )

        except Exception as e:
            elapsed = (time.monotonic() - start) * 1000
            logger.error("ocr_error", error=str(e))
            return ToolResult.error_result(f"OCR failed: {e}")


OCR_TOOLS: list[BaseTool] = [OCRTool()]
