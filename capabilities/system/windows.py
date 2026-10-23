"""T.A.R.O. - Window control capability.

ARCHITECTURE reference: section 14.
RULES reference: section 1, 2, 3, 10.
TASKS: TASK-041.

Tools for window operations: minimize, maximize, restore, close, switch,
resize, and state inspection, routed through winapi adapters.
"""

from __future__ import annotations

from typing import Any

from core.log.setup import get_logger
from core.tools.base import BaseTool, RiskLevel, ToolCategory, ToolResult
from winapi.win32_windows import (
    close_window,
    find_windows,
    get_window_state,
    maximize_window,
    minimize_window,
    resize_window,
    restore_window,
    switch_to_window,
)

logger = get_logger(__name__)


def _resolve_hwnd(kwargs: dict[str, Any]) -> int | None:
    """Helper to get hwnd directly or find by title substring."""
    if "hwnd" in kwargs and kwargs["hwnd"]:
        return int(kwargs["hwnd"])
    title = kwargs.get("title", "")
    if title:
        matches = find_windows(title)
        if matches:
            return matches[0]["hwnd"]
    return None


class WindowControlTool(BaseTool):
    """Controls window state: minimize, maximize, restore, close, switch, resize."""

    name = "window.control"
    description = "Control window state (minimize, maximize, restore, close, switch, resize, get_state)."
    category = ToolCategory.SYSTEM
    risk = RiskLevel.LOW
    timeout_s = 15
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["minimize", "maximize", "restore", "close", "switch", "resize", "get_state", "list"],
                "description": "Window action to perform.",
            },
            "title": {
                "type": "string",
                "description": "Window title substring.",
            },
            "hwnd": {
                "type": "integer",
                "description": "Window handle if known.",
            },
            "width": {"type": "integer", "description": "Target width for resize action."},
            "height": {"type": "integer", "description": "Target height for resize action."},
        },
        "required": ["action"],
    }

    async def run(self, args: dict) -> ToolResult:
        return await self.execute(**args)

    async def execute(self, **kwargs: Any) -> ToolResult:
        action = kwargs.get("action", "").lower()

        if action == "list":
            title_filter = kwargs.get("title", "")
            wins = find_windows(title_filter)
            lines = [f"Found {len(wins)} windows:"]
            for w in wins:
                lines.append(f"- HWND {w['hwnd']}: {w['title']}")
            return ToolResult(status="ok", output="\n".join(lines))

        hwnd = _resolve_hwnd(kwargs)
        if not hwnd:
            return ToolResult(
                status="error",
                output="",
                error=f"No matching window found for title='{kwargs.get('title')}' or hwnd='{kwargs.get('hwnd')}'.",
            )

        if action == "get_state":
            st = get_window_state(hwnd)
            return ToolResult(status="ok", output=f"Window state: {st}")

        elif action == "minimize":
            ok = minimize_window(hwnd)
            st = get_window_state(hwnd)
            return ToolResult(
                status="ok" if ok else "error",
                output=f"Window {hwnd} minimized. Current state: {st.get('state')}",
                error="" if ok else "Failed to minimize window.",
            )

        elif action == "maximize":
            ok = maximize_window(hwnd)
            st = get_window_state(hwnd)
            return ToolResult(
                status="ok" if ok else "error",
                output=f"Window {hwnd} maximized. Current state: {st.get('state')}",
                error="" if ok else "Failed to maximize window.",
            )

        elif action == "restore":
            ok = restore_window(hwnd)
            st = get_window_state(hwnd)
            return ToolResult(
                status="ok" if ok else "error",
                output=f"Window {hwnd} restored. Current state: {st.get('state')}",
                error="" if ok else "Failed to restore window.",
            )

        elif action == "close":
            ok = close_window(hwnd)
            return ToolResult(
                status="ok" if ok else "error",
                output=f"Window {hwnd} close signal sent.",
                error="" if ok else "Failed to close window.",
            )

        elif action == "switch":
            ok = switch_to_window(hwnd)
            return ToolResult(
                status="ok" if ok else "error",
                output=f"Switched focus to window {hwnd}.",
                error="" if ok else "Failed to switch to window.",
            )

        elif action == "resize":
            w = kwargs.get("width", 800)
            h = kwargs.get("height", 600)
            ok = resize_window(hwnd, w, h)
            st = get_window_state(hwnd)
            return ToolResult(
                status="ok" if ok else "error",
                output=f"Window {hwnd} resized to {w}x{h}. Rect: {st.get('rect')}",
                error="" if ok else "Failed to resize window.",
            )

        else:
            return ToolResult(status="error", output="", error=f"Unknown window action: {action}")


WINDOW_TOOLS: list[BaseTool] = [
    WindowControlTool(),
]
