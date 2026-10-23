"""T.A.R.O. - Advanced System Automation Skills.

Provides tools for system management, window control, and power operations.
"""

from __future__ import annotations

import os
import subprocess
from typing import Any

from core.log.setup import get_logger
from core.tools.base import BaseTool, RiskLevel, ToolCategory, ToolResult

logger = get_logger(__name__)


class MaximizeWindowTool(BaseTool):
    """Maximize the active window."""

    name = "window.maximize"
    description = "Maximize the currently active window."
    category = ToolCategory.SYSTEM
    risk = RiskLevel.LOW
    timeout_s = 5
    parameters = {"type": "object", "properties": {}, "required": []}

    async def run(self, args: dict) -> ToolResult:
        return await self.execute(**args)

    async def execute(self, **kwargs: Any) -> ToolResult:
        from pynput.keyboard import Controller, Key
        kbd = Controller()
        try:
            with kbd.pressed(Key.cmd, Key.shift):
                kbd.press(Key.up)
                kbd.release(Key.up)
            return ToolResult(status="ok", output="Maximized active window.")
        except Exception as e:
            return ToolResult(status="error", output="", error=f"Failed to maximize window: {e}")


class MinimizeWindowTool(BaseTool):
    """Minimize the active window."""

    name = "window.minimize"
    description = "Minimize the currently active window."
    category = ToolCategory.SYSTEM
    risk = RiskLevel.LOW
    timeout_s = 5
    parameters = {"type": "object", "properties": {}, "required": []}

    async def run(self, args: dict) -> ToolResult:
        return await self.execute(**args)

    async def execute(self, **kwargs: Any) -> ToolResult:
        from pynput.keyboard import Controller, Key
        kbd = Controller()
        try:
            with kbd.pressed(Key.cmd, Key.shift):
                kbd.press(Key.down)
                kbd.release(Key.down)
            return ToolResult(status="ok", output="Minimized active window.")
        except Exception as e:
            return ToolResult(status="error", output="", error=f"Failed to minimize window: {e}")


class RestoreWindowTool(BaseTool):
    """Restore the active window."""

    name = "window.restore"
    description = "Restore the currently active window from maximized/minimized state."
    category = ToolCategory.SYSTEM
    risk = RiskLevel.LOW
    timeout_s = 5
    parameters = {"type": "object", "properties": {}, "required": []}

    async def run(self, args: dict) -> ToolResult:
        return await self.execute(**args)

    async def execute(self, **kwargs: Any) -> ToolResult:
        from pynput.keyboard import Controller, Key
        kbd = Controller()
        try:
            with kbd.pressed(Key.cmd, Key.shift):
                kbd.press(Key.up)
                kbd.release(Key.up)
            return ToolResult(status="ok", output="Restored active window.")
        except Exception as e:
            return ToolResult(status="error", output="", error=f"Failed to restore window: {e}")


class ShutdownSystemTool(BaseTool):
    """Shutdown the system."""

    name = "system.shutdown"
    description = "Shutdown the computer. Requires user confirmation."
    category = ToolCategory.SYSTEM
    risk = RiskLevel.CRITICAL
    timeout_s = 30
    parameters = {
        "type": "object",
        "properties": {
            "force": {
                "type": "boolean",
                "description": "Force shutdown without waiting for apps to close.",
            },
        },
        "required": [],
    }

    async def run(self, args: dict) -> ToolResult:
        return await self.execute(**args)

    async def execute(self, **kwargs: Any) -> ToolResult:
        force = kwargs.get("force", False)
        
        try:
            if os.name == "nt":
                cmd = ["shutdown", "/s", "/t", "0"] if not force else ["shutdown", "/s", "/f", "/t", "0"]
                subprocess.run(cmd, check=True)
                return ToolResult(status="ok", output="System shutdown initiated.")
            else:
                return ToolResult(status="error", output="", error="Shutdown not supported on this platform.")
        except Exception as e:
            return ToolResult(status="error", output="", error=f"Failed to shutdown: {e}")


class RestartSystemTool(BaseTool):
    """Restart the system."""

    name = "system.restart"
    description = "Restart the computer. Requires user confirmation."
    category = ToolCategory.SYSTEM
    risk = RiskLevel.CRITICAL
    timeout_s = 30
    parameters = {
        "type": "object",
        "properties": {
            "force": {
                "type": "boolean",
                "description": "Force restart without waiting for apps to close.",
            },
        },
        "required": [],
    }

    async def run(self, args: dict) -> ToolResult:
        return await self.execute(**args)

    async def execute(self, **kwargs: Any) -> ToolResult:
        force = kwargs.get("force", False)
        
        try:
            if os.name == "nt":
                cmd = ["shutdown", "/r", "/t", "0"] if not force else ["shutdown", "/r", "/f", "/t", "0"]
                subprocess.run(cmd, check=True)
                return ToolResult(status="ok", output="System restart initiated.")
            else:
                return ToolResult(status="error", output="", error="Restart not supported on this platform.")
        except Exception as e:
            return ToolResult(status="error", output="", error=f"Failed to restart: {e}")


class LockScreenTool(BaseTool):
    """Lock the screen."""

    name = "system.lock_screen"
    description = "Lock the computer screen."
    category = ToolCategory.SYSTEM
    risk = RiskLevel.LOW
    timeout_s = 5
    parameters = {"type": "object", "properties": {}, "required": []}

    async def run(self, args: dict) -> ToolResult:
        return await self.execute(**args)

    async def execute(self, **kwargs: Any) -> ToolResult:
        try:
            if os.name == "nt":
                os.system("rundll32.exe user32.dll,LockWorkStation")
                return ToolResult(status="ok", output="Screen locked.")
            else:
                return ToolResult(status="error", output="", error="Lock screen not supported on this platform.")
        except Exception as e:
            return ToolResult(status="error", output="", error=f"Failed to lock screen: {e}")


class SleepModeTool(BaseTool):
    """Put system to sleep."""

    name = "system.sleep"
    description = "Put the computer to sleep mode."
    category = ToolCategory.SYSTEM
    risk = RiskLevel.LOW
    timeout_s = 10
    parameters = {"type": "object", "properties": {}, "required": []}

    async def run(self, args: dict) -> ToolResult:
        return await self.execute(**args)

    async def execute(self, **kwargs: Any) -> ToolResult:
        try:
            if os.name == "nt":
                os.system("rundll32.exe powrprof.dll,SetSuspendState 0,1,0")
                return ToolResult(status="ok", output="System entering sleep mode.")
            else:
                return ToolResult(status="error", output="", error="Sleep mode not supported on this platform.")
        except Exception as e:
            return ToolResult(status="error", output="", error=f"Failed to enter sleep mode: {e}")


class HibernateSystemTool(BaseTool):
    """Hibernate the system."""

    name = "system.hibernate"
    description = "Hibernate the computer."
    category = ToolCategory.SYSTEM
    risk = RiskLevel.LOW
    timeout_s = 10
    parameters = {"type": "object", "properties": {}, "required": []}

    async def run(self, args: dict) -> ToolResult:
        return await self.execute(**args)

    async def execute(self, **kwargs: Any) -> ToolResult:
        try:
            if os.name == "nt":
                os.system("rundll32.exe powrprof.dll,SetSuspendState Hibernate")
                return ToolResult(status="ok", output="System entering hibernation.")
            else:
                return ToolResult(status="error", output="", error="Hibernate not supported on this platform.")
        except Exception as e:
            return ToolResult(status="error", output="", error=f"Failed to hibernate: {e}")


SYSTEM_ADVANCED_TOOLS: list[BaseTool] = [
    MaximizeWindowTool(),
    MinimizeWindowTool(),
    RestoreWindowTool(),
    ShutdownSystemTool(),
    RestartSystemTool(),
    LockScreenTool(),
    SleepModeTool(),
    HibernateSystemTool(),
]
