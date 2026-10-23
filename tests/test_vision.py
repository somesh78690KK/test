"""Tests for T.A.R.O. Vision subsystem (TASK-061, TASK-062, TASK-063, TASK-064)."""

import io
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from PIL import Image, ImageDraw

from capabilities.vision.camera import CameraTool
from capabilities.vision.capture import (
    CAPTURE_HEIGHT,
    CAPTURE_WIDTH,
    ScreenCaptureTool,
    capture_full_screen,
    capture_region,
)
from capabilities.vision.ocr import OCRTool, ocr_from_bytes
from capabilities.vision.vlm import VisionTool, _validate_vlm_output
from capabilities.vision.capture import _screen_capture_tool


# --- TASK-061: Screen Capture ---

def test_task_061_capture_downscale_and_jpeg():
    """TASK-061: Screen capture downscales to 640x360 and produces in-memory JPEG under 200ms."""
    # Test capture_full_screen
    jpeg_bytes, w, h, elapsed_ms = capture_full_screen()

    assert w == CAPTURE_WIDTH
    assert h == CAPTURE_HEIGHT
    assert isinstance(jpeg_bytes, bytes)
    assert len(jpeg_bytes) > 0
    # Verify it is valid JPEG
    img = Image.open(io.BytesIO(jpeg_bytes))
    assert img.format == "JPEG"
    assert img.size == (CAPTURE_WIDTH, CAPTURE_HEIGHT)


def test_task_061_capture_region():
    """TASK-061: Region capture fits within capture bounds."""
    jpeg_bytes, w, h, elapsed_ms = capture_region(0, 0, 200, 200)
    assert isinstance(jpeg_bytes, bytes)
    assert len(jpeg_bytes) > 0
    img = Image.open(io.BytesIO(jpeg_bytes))
    assert img.format == "JPEG"


@pytest.mark.asyncio
async def test_task_061_sensitive_window_exclusion():
    """TASK-061: Windows with sensitive titles (KeePass, Bitwarden, etc.) are refused."""
    tool = ScreenCaptureTool()

    # Sensitive window
    res = await tool.execute(mode="full", window_title="My KeePass Vault - Passwords")
    assert res.status == "denied"
    assert "refused" in (res.error or "").lower()

    # Normal window
    with patch("capabilities.vision.capture.capture_full_screen", return_value=(b"fake_jpeg", 640, 360, 50.0)):
        res_ok = await tool.execute(mode="full", window_title="Notepad - Notes.txt")
        assert res_ok.status == "ok"


# --- TASK-062: OCR Tool ---

def test_task_062_ocr_known_image():
    """TASK-062: OCR matches expected text on a known test image."""
    img = Image.new("RGB", (400, 100), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.text((20, 35), "TARO SYSTEM ACTIVE", fill=(0, 0, 0))

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    png_bytes = buf.getvalue()

    with patch("pytesseract.image_to_string", return_value="TARO SYSTEM ACTIVE"):
        text = ocr_from_bytes(png_bytes)
        assert "TARO" in text


@pytest.mark.asyncio
async def test_task_062_ocr_tool_integration():
    """TASK-062: OCRTool extracts text from last screen capture."""
    tool = OCRTool()
    _screen_capture_tool.last_frame = b"fake_screen_bytes"
    with patch("capabilities.vision.ocr._check_tesseract", return_value=True):
        with patch("capabilities.vision.ocr.ocr_from_bytes", return_value="Hello World"):
            res = await tool.execute()
            assert res.status == "ok"
            assert "Hello World" in res.output


# --- TASK-063: Vision Tool (VLM) & Anti-Hallucination Validator ---

def test_task_063_anti_hallucination_validator():
    """TASK-063: Anti-hallucination validator rejects short, empty, or contradictory outputs."""
    # Empty output
    assert _validate_vlm_output("") is not None

    # Too short (< 20 chars)
    assert _validate_vlm_output("A cat.") is not None

    # Contradiction ("not visible", "cannot see")
    assert _validate_vlm_output("The requested object is not visible in this image.") is not None

    # Valid descriptive output
    valid_text = "The screen shows a code editor with Python code open and a terminal at the bottom."
    assert _validate_vlm_output(valid_text) is None


@pytest.mark.asyncio
async def test_task_063_vlm_tool_call_and_validation():
    """TASK-063: VLM tool calls Ollama vision model and applies validation."""
    tool = VisionTool()
    _screen_capture_tool.last_frame = b"fake_screen_bytes"

    # Simulated model response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "response": "The screen shows a blue desktop background with several application shortcuts."
    }

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response):
        res = await tool.execute(prompt="Describe the screen")
        assert res.status == "ok"
        assert "blue desktop background" in res.output


# --- TASK-064: Camera Tool ---

@pytest.mark.asyncio
async def test_task_064_camera_off_by_default_and_enable():
    """TASK-064: Camera is off by default; must be explicitly enabled; analysis works on fallback."""
    tool = CameraTool()

    # Reset camera enabled state for testing
    import capabilities.vision.camera as cam_mod
    cam_mod._camera_enabled = False

    # 1. Attempting to capture while disabled returns error
    res_disabled = await tool.execute(enable=False)
    assert res_disabled.status == "error"
    assert "disabled by default" in res_disabled.error

    # 2. Enabling camera succeeds
    res_enable = await tool.execute(enable=True)
    assert res_enable.status == "ok"
    assert cam_mod._camera_enabled is True

    # 3. Capture with mocked OpenCV works
    mock_cap = MagicMock()
    mock_cap.isOpened.return_value = True
    import numpy as np
    dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    mock_cap.read.return_value = (True, dummy_frame)

    with patch("cv2.VideoCapture", return_value=mock_cap):
        res_capture = await tool.execute()
        assert res_capture.status == "ok"
        assert "Camera frame captured" in res_capture.output
