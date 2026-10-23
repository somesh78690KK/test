"""T.A.R.O. - Browser Automation Skills.

Provides tools for browser tab management, navigation, and basic automation.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

from core.log.setup import get_logger
from core.tools.base import BaseTool, RiskLevel, ToolCategory, ToolResult

logger = get_logger(__name__)


class BrowserCloseTabTool(BaseTool):
    """Close the current browser tab."""

    name = "browser.close_tab"
    description = "Close the current browser tab."
    category = ToolCategory.BROWSER
    risk = RiskLevel.LOW
    timeout_s = 5
    parameters = {"type": "object", "properties": {}, "required": []}

    parameters = {"type": "object", "properties": {}, "required": []}

    async def run(self, args: dict) -> ToolResult:
        return await self.execute(**args)

    async def execute(self, **kwargs: Any) -> ToolResult:
        from pynput.keyboard import Controller, Key
        kbd = Controller()
        try:
            with kbd.pressed(Key.ctrl):
                kbd.press('w')
                kbd.release('w')
            return ToolResult(status="ok", output="Closed current browser tab.")
        except Exception as e:
            return ToolResult(status="error", output="", error=f"Failed to close tab: {e}")


class BrowserNewTabTool(BaseTool):
    """Open a new browser tab."""

    name = "browser.new_tab"
    description = "Open a new browser tab."
    category = ToolCategory.BROWSER
    risk = RiskLevel.LOW
    timeout_s = 5

    parameters = {"type": "object", "properties": {}, "required": []}

    async def run(self, args: dict) -> ToolResult:
        return await self.execute(**args)

    async def execute(self, **kwargs: Any) -> ToolResult:
        from pynput.keyboard import Controller, Key
        kbd = Controller()
        try:
            with kbd.pressed(Key.ctrl):
                kbd.press('t')
                kbd.release('t')
            return ToolResult(status="ok", output="Opened new browser tab.")
        except Exception as e:
            return ToolResult(status="error", output="", error=f"Failed to open new tab: {e}")


class BrowserReopenTabTool(BaseTool):
    """Reopen the last closed browser tab."""

    name = "browser.reopen_tab"
    description = "Reopen the last closed browser tab."
    category = ToolCategory.BROWSER
    risk = RiskLevel.LOW
    timeout_s = 5

    parameters = {"type": "object", "properties": {}, "required": []}

    async def run(self, args: dict) -> ToolResult:
        return await self.execute(**args)

    async def execute(self, **kwargs: Any) -> ToolResult:
        from pynput.keyboard import Controller, Key
        kbd = Controller()
        try:
            with kbd.pressed(Key.ctrl, Key.shift):
                kbd.press('t')
                kbd.release('t')
            return ToolResult(status="ok", output="Reopened last closed tab.")
        except Exception as e:
            return ToolResult(status="error", output="", error=f"Failed to reopen tab: {e}")


class BrowserGoBackTool(BaseTool):
    """Navigate back in browser history."""

    name = "browser.go_back"
    description = "Navigate back to the previous page in browser history."
    category = ToolCategory.BROWSER
    risk = RiskLevel.LOW
    timeout_s = 5

    parameters = {"type": "object", "properties": {}, "required": []}

    async def run(self, args: dict) -> ToolResult:
        return await self.execute(**args)

    async def execute(self, **kwargs: Any) -> ToolResult:
        from pynput.keyboard import Controller, Key
        kbd = Controller()
        try:
            with kbd.pressed(Key.alt):
                kbd.press(Key.left)
                kbd.release(Key.left)
            return ToolResult(status="ok", output="Navigated back in browser history.")
        except Exception as e:
            return ToolResult(status="error", output="", error=f"Failed to navigate back: {e}")


class BrowserGoForwardTool(BaseTool):
    """Navigate forward in browser history."""

    name = "browser.go_forward"
    description = "Navigate forward to the next page in browser history."
    category = ToolCategory.BROWSER
    risk = RiskLevel.LOW
    timeout_s = 5

    parameters = {"type": "object", "properties": {}, "required": []}

    async def run(self, args: dict) -> ToolResult:
        return await self.execute(**args)

    async def execute(self, **kwargs: Any) -> ToolResult:
        from pynput.keyboard import Controller, Key
        kbd = Controller()
        try:
            with kbd.pressed(Key.alt):
                kbd.press(Key.right)
                kbd.release(Key.right)
            return ToolResult(status="ok", output="Navigated forward in browser history.")
        except Exception as e:
            return ToolResult(status="error", output="", error=f"Failed to navigate forward: {e}")


class BrowserPageUpTool(BaseTool):
    """Scroll up one page in the browser."""

    name = "browser.page_up"
    description = "Scroll up one page in the browser."
    category = ToolCategory.BROWSER
    risk = RiskLevel.LOW
    timeout_s = 5

    parameters = {"type": "object", "properties": {}, "required": []}

    async def run(self, args: dict) -> ToolResult:
        return await self.execute(**args)

    async def execute(self, **kwargs: Any) -> ToolResult:
        from pynput.keyboard import Controller, Key
        kbd = Controller()
        try:
            kbd.press(Key.page_up)
            kbd.release(Key.page_up)
            return ToolResult(status="ok", output="Scrolled up one page.")
        except Exception as e:
            return ToolResult(status="error", output="", error=f"Failed to scroll up: {e}")


class BrowserPageDownTool(BaseTool):
    """Scroll down one page in the browser."""

    name = "browser.page_down"
    description = "Scroll down one page in the browser."
    category = ToolCategory.BROWSER
    risk = RiskLevel.LOW
    timeout_s = 5

    parameters = {"type": "object", "properties": {}, "required": []}

    async def run(self, args: dict) -> ToolResult:
        return await self.execute(**args)

    async def execute(self, **kwargs: Any) -> ToolResult:
        from pynput.keyboard import Controller, Key
        kbd = Controller()
        try:
            kbd.press(Key.page_down)
            kbd.release(Key.page_down)
            return ToolResult(status="ok", output="Scrolled down one page.")
        except Exception as e:
            return ToolResult(status="error", output="", error=f"Failed to scroll down: {e}")


class BrowserJumpTopTool(BaseTool):
    """Jump to the top of the page."""

    name = "browser.jump_top"
    description = "Jump to the top of the current page."
    category = ToolCategory.BROWSER
    risk = RiskLevel.LOW
    timeout_s = 5

    parameters = {"type": "object", "properties": {}, "required": []}

    async def run(self, args: dict) -> ToolResult:
        return await self.execute(**args)

    async def execute(self, **kwargs: Any) -> ToolResult:
        from pynput.keyboard import Controller, Key
        kbd = Controller()
        try:
            kbd.press(Key.home)
            kbd.release(Key.home)
            return ToolResult(status="ok", output="Jumped to top of page.")
        except Exception as e:
            return ToolResult(status="error", output="", error=f"Failed to jump to top: {e}")


class BrowserJumpBottomTool(BaseTool):
    """Jump to the bottom of the page."""

    name = "browser.jump_bottom"
    description = "Jump to the bottom of the current page."
    category = ToolCategory.BROWSER
    risk = RiskLevel.LOW
    timeout_s = 5

    parameters = {"type": "object", "properties": {}, "required": []}

    async def run(self, args: dict) -> ToolResult:
        return await self.execute(**args)

    async def execute(self, **kwargs: Any) -> ToolResult:
        from pynput.keyboard import Controller, Key
        kbd = Controller()
        try:
            kbd.press(Key.end)
            kbd.release(Key.end)
            return ToolResult(status="ok", output="Jumped to bottom of page.")
        except Exception as e:
            return ToolResult(status="error", output="", error=f"Failed to jump to bottom: {e}")


class BrowserFocusUrlTool(BaseTool):
    """Focus the browser URL bar."""

    name = "browser.focus_url"
    description = "Focus the browser URL/address bar for typing a new URL."
    category = ToolCategory.BROWSER
    risk = RiskLevel.LOW
    timeout_s = 5

    parameters = {"type": "object", "properties": {}, "required": []}

    async def run(self, args: dict) -> ToolResult:
        return await self.execute(**args)

    async def execute(self, **kwargs: Any) -> ToolResult:
        from pynput.keyboard import Controller, Key
        kbd = Controller()
        try:
            with kbd.pressed(Key.ctrl):
                kbd.press('l')
                kbd.release('l')
            return ToolResult(status="ok", output="Focused URL bar.")
        except Exception as e:
            return ToolResult(status="error", output="", error=f"Failed to focus URL bar: {e}")


class BrowserOpenDevToolsTool(BaseTool):
    """Open browser developer tools."""

    name = "browser.open_devtools"
    description = "Open browser developer tools (F12)."
    category = ToolCategory.BROWSER
    risk = RiskLevel.LOW
    timeout_s = 5

    parameters = {"type": "object", "properties": {}, "required": []}

    async def run(self, args: dict) -> ToolResult:
        return await self.execute(**args)

    async def execute(self, **kwargs: Any) -> ToolResult:
        from pynput.keyboard import Controller, Key
        kbd = Controller()
        try:
            kbd.press(Key.f12)
            kbd.release(Key.f12)
            return ToolResult(status="ok", output="Opened developer tools.")
        except Exception as e:
            return ToolResult(status="error", output="", error=f"Failed to open dev tools: {e}")


BROWSER_AUTOMATION_TOOLS: list[BaseTool] = [
    BrowserCloseTabTool(),
    BrowserNewTabTool(),
    BrowserReopenTabTool(),
    BrowserGoBackTool(),
    BrowserGoForwardTool(),
    BrowserPageUpTool(),
    BrowserPageDownTool(),
    BrowserJumpTopTool(),
    BrowserJumpBottomTool(),
    BrowserFocusUrlTool(),
    BrowserOpenDevToolsTool(),
]
