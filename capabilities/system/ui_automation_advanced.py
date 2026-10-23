"""T.A.R.O. - Advanced UI Automation Skills.

Provides tools for UI element interaction, clicking, and text input.
"""

from __future__ import annotations

import asyncio
from typing import Any

from core.log.setup import get_logger
from core.tools.base import BaseTool, RiskLevel, ToolCategory, ToolResult

logger = get_logger(__name__)


class TypeTextTool(BaseTool):
    """Type text at the current cursor position."""

    name = "ui.type_text"
    description = "Type text at the current cursor position."
    category = ToolCategory.SYSTEM
    risk = RiskLevel.LOW
    timeout_s = 10
    parameters = {
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "Text to type.",
            },
        },
        "required": ["text"],
    }

    async def run(self, args: dict) -> ToolResult:
        return await self.execute(**args)

    async def execute(self, **kwargs: Any) -> ToolResult:
        text = kwargs.get("text", "").strip()
        
        if not text:
            return ToolResult(status="error", output="", error="Missing 'text' argument.")
        
        try:
            from pynput.keyboard import Controller
            kbd = Controller()
            kbd.type(text)
            return ToolResult(status="ok", output=f"Typed text: '{text[:50]}...'")
        except Exception as e:
            return ToolResult(status="error", output="", error=f"Failed to type text: {e}")


class PressKeyTool(BaseTool):
    """Press a specific keyboard key."""

    name = "ui.press_key"
    description = "Press a specific keyboard key (e.g., 'enter', 'escape', 'f5')."
    category = ToolCategory.SYSTEM
    risk = RiskLevel.LOW
    timeout_s = 5
    parameters = {
        "type": "object",
        "properties": {
            "key": {
                "type": "string",
                "description": "Key to press (e.g., 'enter', 'escape', 'f5', 'tab').",
            },
        },
        "required": ["key"],
    }

    async def run(self, args: dict) -> ToolResult:
        return await self.execute(**args)

    async def execute(self, **kwargs: Any) -> ToolResult:
        key_name = kwargs.get("key", "").strip().lower()
        
        if not key_name:
            return ToolResult(status="error", output="", error="Missing 'key' argument.")
        
        try:
            from pynput.keyboard import Controller, Key
            kbd = Controller()
            
            # Map common key names
            key_map = {
                'enter': Key.enter,
                'return': Key.enter,
                'escape': Key.esc,
                'tab': Key.tab,
                'space': Key.space,
                'backspace': Key.backspace,
                'delete': Key.delete,
                'home': Key.home,
                'end': Key.end,
                'page_up': Key.page_up,
                'page_down': Key.page_down,
                'up': Key.up,
                'down': Key.down,
                'left': Key.left,
                'right': Key.right,
            }
            
            key_obj = key_map.get(key_name, key_name)
            kbd.press(key_obj)
            kbd.release(key_obj)
            
            return ToolResult(status="ok", output=f"Pressed key: {key_name}")
        except Exception as e:
            return ToolResult(status="error", output="", error=f"Failed to press key: {e}")


class PressHotkeyTool(BaseTool):
    """Press a keyboard hotkey combination."""

    name = "ui.press_hotkey"
    description = "Press a keyboard hotkey combination (e.g., 'ctrl+c', 'alt+f4')."
    category = ToolCategory.SYSTEM
    risk = RiskLevel.LOW
    timeout_s = 5
    parameters = {
        "type": "object",
        "properties": {
            "hotkey": {
                "type": "string",
                "description": "Hotkey combination (e.g., 'ctrl+c', 'alt+f4', 'ctrl+shift+esc').",
            },
        },
        "required": ["hotkey"],
    }

    async def run(self, args: dict) -> ToolResult:
        return await self.execute(**args)

    async def execute(self, **kwargs: Any) -> ToolResult:
        hotkey = kwargs.get("hotkey", "").strip()
        
        if not hotkey:
            return ToolResult(status="error", output="", error="Missing 'hotkey' argument.")
        
        try:
            from pynput.keyboard import Controller, Key
            kbd = Controller()
            
            # Parse hotkey
            parts = hotkey.lower().split('+')
            keys = []
            
            for part in parts:
                if part == 'ctrl':
                    keys.append(Key.ctrl)
                elif part == 'alt':
                    keys.append(Key.alt)
                elif part == 'shift':
                    keys.append(Key.shift)
                elif part == 'cmd' or part == 'win':
                    keys.append(Key.cmd)
                elif part == 'enter':
                    keys.append(Key.enter)
                elif part == 'tab':
                    keys.append(Key.tab)
                elif part == 'esc':
                    keys.append(Key.esc)
                elif part == 'space':
                    keys.append(Key.space)
                else:
                    keys.append(part)
            
            # Press all keys together
            with kbd.pressed(*keys):
                pass
            # Release
            for key in keys:
                if isinstance(key, str):
                    kbd.release(key)
                else:
                    kbd.release(key)
            
            return ToolResult(status="ok", output=f"Pressed hotkey: {hotkey}")
        except Exception as e:
            return ToolResult(status="error", output="", error=f"Failed to press hotkey: {e}")


UI_AUTOMATION_ADVANCED_TOOLS: list[BaseTool] = [
    TypeTextTool(),
    PressKeyTool(),
    PressHotkeyTool(),
]
