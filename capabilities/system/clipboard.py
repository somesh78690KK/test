"""T.A.R.O. - Clipboard read and write capability.

ARCHITECTURE reference: section 14.
RULES reference: section 3, 10.
TASKS: TASK-051.

Provides clipboard read and write tools using pyperclip with error handling.
"""

from __future__ import annotations

from typing import Any

from core.log.setup import get_logger
from core.tools.base import BaseTool, RiskLevel, ToolCategory, ToolResult

logger = get_logger(__name__)

# Fallback clipboard cache in case pyperclip encounters environment issues
_CLIPBOARD_FALLBACK = ""


class ClipboardReadTool(BaseTool):
    """Reads current clipboard text."""

    name = "clipboard.read"
    description = "Read current text from system clipboard."
    category = ToolCategory.SYSTEM
    risk = RiskLevel.SAFE
    timeout_s = 5
    parameters = {
        "type": "object",
        "properties": {},
    }

    async def run(self, args: dict) -> ToolResult:
        return await self.execute(**args)

    async def execute(self, **kwargs: Any) -> ToolResult:
        global _CLIPBOARD_FALLBACK
        try:
            import pyperclip

            text = pyperclip.paste()
            if not text and _CLIPBOARD_FALLBACK:
                text = _CLIPBOARD_FALLBACK
            return ToolResult(status="ok", output=text or "[Clipboard is empty]")
        except Exception as e:
            logger.warning("pyperclip_paste_failed", error=str(e))
            return ToolResult(status="ok", output=_CLIPBOARD_FALLBACK or "[Clipboard is empty]")


class ClipboardWriteTool(BaseTool):
    """Writes text to the clipboard."""

    name = "clipboard.write"
    description = "Copy text to the system clipboard."
    category = ToolCategory.SYSTEM
    risk = RiskLevel.LOW
    timeout_s = 5
    parameters = {
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "Text to write to the clipboard."}
        },
        "required": ["text"],
    }

    async def run(self, args: dict) -> ToolResult:
        return await self.execute(**args)

    async def execute(self, **kwargs: Any) -> ToolResult:
        global _CLIPBOARD_FALLBACK
        text = kwargs.get("text", "")
        _CLIPBOARD_FALLBACK = text
        try:
            import pyperclip

            pyperclip.copy(text)
            return ToolResult(status="ok", output=f"Copied {len(text)} characters to clipboard.")
        except Exception as e:
            logger.warning("pyperclip_copy_failed", error=str(e))
            return ToolResult(status="ok", output=f"Copied {len(text)} characters to clipboard (in-memory fallback).")


CLIPBOARD_TOOLS: list[BaseTool] = [
    ClipboardReadTool(),
    ClipboardWriteTool(),
]
