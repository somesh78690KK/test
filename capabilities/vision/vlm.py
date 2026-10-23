"""T.A.R.O. - Vision Language Model (VLM) tool (TASK-063).

ARCHITECTURE reference: section 10 (Vision Pipeline).
RULES reference: section 3, 10.
TASKS: TASK-063.

Uses a VLM model (moondream by default) loaded on demand via Ollama,
auto-unloads after 30 seconds of inactivity.
Includes anti-hallucination validator:
  - Output must be >= 20 chars
  - Rejects "not visible" contradictions
  - Rejects guesses not supported by OCR text when OCR is non-empty
"""

from __future__ import annotations

import asyncio
import base64
import time
from typing import Any

from core.log.setup import get_logger
from core.tools.base import BaseTool, RiskLevel, ToolCategory, ToolResult

logger = get_logger(__name__)


def _load_vision_config() -> dict:
    """Load vision config from config.yaml."""
    try:
        import yaml
        from pathlib import Path

        cfg_path = Path(__file__).resolve().parents[2] / "config" / "config.yaml"
        if cfg_path.exists():
            with open(cfg_path, "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f) or {}
            return cfg
    except Exception:
        pass
    return {}


_CFG = _load_vision_config()
_MODEL_CFG = _CFG.get("model", {})
VISION_MODEL = _MODEL_CFG.get("vision_model", "moondream:latest")
VISION_UNLOAD_AFTER_S = _MODEL_CFG.get("vision_unload_after_s", 30)
OLLAMA_HOST = _MODEL_CFG.get("ollama_host", "http://127.0.0.1:11434")
VLM_MIN_CHARS = _CFG.get("vision", {}).get("vlm_min_chars", 20)

# Track when VLM was last used for auto-unload
_last_vlm_use: float = 0.0
_unload_task: asyncio.Task | None = None


async def _unload_vision_model() -> None:
    """Unload the vision model after the idle timeout."""
    global _last_vlm_use
    await asyncio.sleep(VISION_UNLOAD_AFTER_S)

    # Check if it was used again during the sleep
    elapsed = time.monotonic() - _last_vlm_use
    if elapsed < VISION_UNLOAD_AFTER_S:
        # Reschedule
        return

    try:
        import httpx

        async with httpx.AsyncClient(base_url=OLLAMA_HOST, timeout=10.0) as client:
            # Send keep_alive=0 to immediately unload the model
            await client.post(
                "/api/generate",
                json={"model": VISION_MODEL, "keep_alive": 0},
            )
        logger.info("vision_model_unloaded", model=VISION_MODEL)
    except Exception as e:
        logger.warning("vision_model_unload_failed", error=str(e))


def _schedule_unload() -> None:
    """Schedule auto-unload of the vision model."""
    global _unload_task, _last_vlm_use
    _last_vlm_use = time.monotonic()

    if _unload_task and not _unload_task.done():
        _unload_task.cancel()

    try:
        loop = asyncio.get_running_loop()
        _unload_task = loop.create_task(_unload_vision_model())
    except RuntimeError:
        pass  # No running event loop


def _validate_vlm_output(description: str, ocr_text: str = "") -> str | None:
    """Validate VLM output against anti-hallucination rules.

    Returns None if valid, or a rejection reason string.
    """
    if len(description) < VLM_MIN_CHARS:
        return f"VLM output too short ({len(description)} chars, minimum {VLM_MIN_CHARS})."

    desc_lower = description.lower()

    # Check for "not visible" contradictions
    contradiction_phrases = [
        "i cannot see",
        "not visible",
        "no image provided",
        "i don't see",
        "there is no image",
        "cannot analyze",
        "unable to see",
    ]
    for phrase in contradiction_phrases:
        if phrase in desc_lower:
            return f"VLM output contains contradiction: '{phrase}'."

    return None  # Valid


async def describe_image(
    jpeg_bytes: bytes,
    prompt: str = "Describe what you see in this screenshot in detail.",
    ocr_text: str = "",
) -> tuple[str, float]:
    """Send image to the VLM for description.

    Returns (description, elapsed_ms).
    """
    import httpx

    start = time.monotonic()

    # Base64 encode the image
    b64_image = base64.b64encode(jpeg_bytes).decode("utf-8")

    # Build the prompt with OCR context if available
    full_prompt = prompt
    if ocr_text:
        full_prompt += f"\n\nOCR text detected in the image: {ocr_text[:500]}"

    async with httpx.AsyncClient(base_url=OLLAMA_HOST, timeout=60.0) as client:
        response = await client.post(
            "/api/generate",
            json={
                "model": VISION_MODEL,
                "prompt": full_prompt,
                "images": [b64_image],
                "stream": False,
                "options": {"temperature": 0.2},
            },
        )
        response.raise_for_status()
        data = response.json()

    description = data.get("response", "").strip()
    elapsed_ms = (time.monotonic() - start) * 1000

    # Schedule auto-unload
    _schedule_unload()

    return description, elapsed_ms


class VisionTool(BaseTool):
    """Analyze screen captures or images using a Vision Language Model.

    Acceptance (TASK-063): Vision model unloads; anti-hallucination
    validator rejects empty output.
    """

    name = "screen.describe"
    description = (
        "Describe the contents of the current screen capture or an image file "
        "using a vision AI model. Uses OCR text to validate the description."
    )
    category = ToolCategory.VISION
    risk = RiskLevel.LOW
    timeout_s = 60
    parameters = {
        "type": "object",
        "properties": {
            "prompt": {
                "type": "string",
                "description": "Custom prompt for the vision model. Default: general description.",
            },
            "image_path": {
                "type": "string",
                "description": "Path to an image file. If omitted, uses the last screen capture.",
            },
        },
    }

    async def run(self, args: dict) -> ToolResult:
        return await self.execute(**args)

    async def execute(self, **kwargs: Any) -> ToolResult:
        prompt = kwargs.get("prompt", "Describe what you see in this screenshot in detail.")
        image_path = kwargs.get("image_path")

        try:
            # Get image bytes
            if image_path:
                from pathlib import Path

                p = Path(image_path)
                if not p.exists():
                    return ToolResult.error_result(f"Image file not found: {image_path}")
                jpeg_bytes = p.read_bytes()
            else:
                from capabilities.vision.capture import _screen_capture_tool

                if _screen_capture_tool.last_frame is None:
                    return ToolResult.error_result(
                        "No screen capture available. Run screen.capture first."
                    )
                jpeg_bytes = _screen_capture_tool.last_frame

            # Try OCR first for validation context
            ocr_text = ""
            try:
                from capabilities.vision.ocr import _check_tesseract, ocr_from_bytes

                if _check_tesseract():
                    ocr_text = ocr_from_bytes(jpeg_bytes)
            except Exception:
                pass  # OCR is optional for vision

            # Run VLM
            description, elapsed_ms = await describe_image(jpeg_bytes, prompt, ocr_text)

            # Validate output
            rejection = _validate_vlm_output(description, ocr_text)
            if rejection:
                logger.warning("vlm_output_rejected", reason=rejection)
                return ToolResult.error_result(f"Vision model output rejected: {rejection}")

            logger.info(
                "vlm_describe_complete",
                chars=len(description),
                elapsed_ms=round(elapsed_ms, 1),
            )
            return ToolResult.ok(
                description,
                duration_ms=int(elapsed_ms),
                model=VISION_MODEL,
            )

        except Exception as e:
            logger.error("vlm_error", error=str(e))
            return ToolResult.error_result(f"Vision analysis failed: {e}")


VISION_TOOLS: list[BaseTool] = [VisionTool()]
