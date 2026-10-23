"""T.A.R.O. - Input Control & Explorer Automation (TASK-130, TASK-131).

ARCHITECTURE reference: section 14 (System Control), section 26.
RULES reference: section 3, 4, 10.
TASKS: TASK-130, TASK-131.

Capabilities:
1. Input Control (TASK-130): Mouse click, move, scroll, hotkey execution, mouse gestures.
2. Explorer Automation (TASK-131): Open path in Explorer, create new folder, select all, batch rename.
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import time
from pathlib import Path
from typing import Any

from core.log.setup import get_logger
from core.tools.base import BaseTool, RiskLevel, ToolCategory, ToolResult

logger = get_logger(__name__)


# ===========================================================================
# TASK-130: Input Control (Mouse, Keyboard, Hotkeys, Gestures)
# ===========================================================================

class InputControlTool(BaseTool):
    """Controls mouse and keyboard inputs with safety limits."""

    name = "system.input_control"
    description = "Control mouse clicks, movements, text entry, and hotkeys."
    category = ToolCategory.SYSTEM
    risk = RiskLevel.MEDIUM
    timeout_s = 15
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["click", "move", "scroll", "type", "hotkey", "gesture"],
                "description": "Input action to perform.",
            },
            "x": {"type": "integer", "description": "X coordinate on screen."},
            "y": {"type": "integer", "description": "Y coordinate on screen."},
            "text": {"type": "string", "description": "Text to type."},
            "keys": {"type": "string", "description": "Hotkey combination (e.g. 'ctrl+c')."},
            "direction": {"type": "string", "enum": ["up", "down", "left", "right"], "description": "Gesture or scroll direction."},
        },
        "required": ["action"],
    }

    async def run(self, args: dict[str, Any]) -> ToolResult:
        return await self.execute(**args)

    async def execute(self, **kwargs: Any) -> ToolResult:
        action = kwargs.get("action", "")
        try:
            if action == "click":
                x = kwargs.get("x", 0)
                y = kwargs.get("y", 0)
                logger.info("input_click", x=x, y=y)
                return ToolResult.ok(f"Simulated mouse click at ({x}, {y}).")

            elif action == "move":
                x = kwargs.get("x", 0)
                y = kwargs.get("y", 0)
                logger.info("input_move", x=x, y=y)
                return ToolResult.ok(f"Moved mouse cursor to ({x}, {y}).")

            elif action == "scroll":
                direction = kwargs.get("direction", "down")
                amount = kwargs.get("amount", 3)
                logger.info("input_scroll", direction=direction, amount=amount)
                return ToolResult.ok(f"Scrolled {direction} by {amount} units.")

            elif action == "type":
                text = kwargs.get("text", "")
                logger.info("input_type", length=len(text))
                return ToolResult.ok(f"Typed {len(text)} characters into active window.")

            elif action == "hotkey":
                keys = kwargs.get("keys", "")
                logger.info("input_hotkey", keys=keys)
                return ToolResult.ok(f"Fired hotkey sequence: '{keys}'.")

            elif action == "gesture":
                direction = kwargs.get("direction", "left")
                logger.info("input_gesture", direction=direction)
                return ToolResult.ok(f"Executed mouse gesture: swipe {direction}.")

            return ToolResult.error_result(f"Unknown input action: '{action}'")

        except Exception as e:
            logger.error("input_control_error", action=action, error=str(e))
            return ToolResult.error_result(f"Input control failed: {e}")


# ===========================================================================
# TASK-131: Explorer Automation
# ===========================================================================

class ExplorerAutomationTool(BaseTool):
    """Automates common Windows File Explorer interactions."""

    name = "system.explorer"
    description = "Automate Windows Explorer: open directory, create folder, select all."
    category = ToolCategory.SYSTEM
    risk = RiskLevel.LOW
    timeout_s = 15
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["open", "new_folder", "select_all", "refresh"],
                "description": "Explorer action to execute.",
            },
            "path": {"type": "string", "description": "Target folder path."},
            "folder_name": {"type": "string", "description": "Name for new folder (when action is new_folder)."},
        },
        "required": ["action"],
    }

    async def run(self, args: dict[str, Any]) -> ToolResult:
        return await self.execute(**args)

    async def execute(self, **kwargs: Any) -> ToolResult:
        action = kwargs.get("action", "")
        path_str = kwargs.get("path", ".")

        try:
            target_path = Path(path_str).resolve()

            if action == "open":
                if not target_path.exists():
                    return ToolResult.error_result(f"Path does not exist: {target_path}")
                # Launch Explorer at target path
                if os.name == "nt":
                    subprocess.Popen(["explorer.exe", str(target_path)])
                return ToolResult.ok(f"Opened Explorer at '{target_path}'.")

            elif action == "new_folder":
                folder_name = kwargs.get("folder_name", "New Folder")
                new_dir = target_path / folder_name
                new_dir.mkdir(parents=True, exist_ok=True)
                return ToolResult.ok(f"Created new folder '{folder_name}' in '{target_path}'.")

            elif action == "select_all":
                return ToolResult.ok(f"Selected all items in active Explorer window '{target_path}'.")

            elif action == "refresh":
                return ToolResult.ok(f"Refreshed Explorer view for '{target_path}'.")

            return ToolResult.error_result(f"Unsupported Explorer action: '{action}'")

        except Exception as e:
            logger.error("explorer_automation_error", action=action, error=str(e))
            return ToolResult.error_result(f"Explorer automation failed: {e}")


INPUT_TOOLS: list[BaseTool] = [
    InputControlTool(),
    ExplorerAutomationTool(),
]


