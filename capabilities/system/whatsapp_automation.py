"""T.A.R.O. - WhatsApp Automation Skills.

Provides tools for WhatsApp chat management and automation.
"""

from __future__ import annotations

import asyncio
from typing import Any

from core.log.setup import get_logger
from core.tools.base import BaseTool, RiskLevel, ToolCategory, ToolResult

logger = get_logger(__name__)


class WhatsAppNewChatTool(BaseTool):
    """Open a new chat in WhatsApp."""

    name = "whatsapp.new_chat"
    description = "Open a new chat window in WhatsApp."
    category = ToolCategory.SYSTEM
    risk = RiskLevel.LOW
    timeout_s = 10
    parameters = {"type": "object", "properties": {}, "required": []}

    async def run(self, args: dict) -> ToolResult:
        return await self.execute(**args)

    async def execute(self, **kwargs: Any) -> ToolResult:
        try:
            from pynput.keyboard import Controller, Key
            kbd = Controller()
            
            # Focus WhatsApp first
            import os
            os.startfile("whatsapp:")
            await asyncio.sleep(1.5)
            
            # Open new chat (Ctrl+N)
            with kbd.pressed(Key.ctrl):
                kbd.press('n')
                kbd.release('n')
            
            return ToolResult(status="ok", output="Opened new WhatsApp chat.")
        except Exception as e:
            return ToolResult(status="error", output="", error=f"Failed to open new chat: {e}")


class WhatsAppSearchChatTool(BaseTool):
    """Search for a chat in WhatsApp."""

    name = "whatsapp.search_chat"
    description = "Search for a specific chat in WhatsApp by name."
    category = ToolCategory.SYSTEM
    risk = RiskLevel.LOW
    timeout_s = 10
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Chat name or phone number to search for.",
            },
        },
        "required": ["query"],
    }

    async def run(self, args: dict) -> ToolResult:
        return await self.execute(**args)

    async def execute(self, **kwargs: Any) -> ToolResult:
        query = kwargs.get("query", "").strip()
        
        if not query:
            return ToolResult(status="error", output="", error="Missing 'query' argument.")
        
        try:
            from pynput.keyboard import Controller, Key
            kbd = Controller()
            
            # Focus WhatsApp
            import os
            os.startfile("whatsapp:")
            await asyncio.sleep(1.5)
            
            # Focus search (Ctrl+F)
            with kbd.pressed(Key.ctrl):
                kbd.press('f')
                kbd.release('f')
            await asyncio.sleep(0.5)
            
            # Type search query
            kbd.type(query)
            await asyncio.sleep(0.5)
            
            # Press Enter to select
            kbd.press(Key.enter)
            kbd.release(Key.enter)
            
            return ToolResult(status="ok", output=f"Searched for chat: {query}")
        except Exception as e:
            return Tool(status="error", output="", error=f"Failed to search chat: {e}")


class WhatsAppNextChatTool(BaseTool):
    """Navigate to the next chat in WhatsApp."""

    name = "whatsapp.next_chat"
    description = "Navigate to the next chat in WhatsApp chat list."
    category = ToolCategory.SYSTEM
    risk = RiskLevel.LOW
    timeout_s = 5
    parameters = {"type": "object", "properties": {}, "required": []}

    async def run(self, args: dict) -> ToolResult:
        return await self.execute(**args)

    async def execute(self, **kwargs: Any) -> ToolResult:
        try:
            from pynput.keyboard import Controller, Key
            kbd = Controller()
            
            # Navigate down in chat list (Ctrl+Tab)
            with kbd.pressed(Key.ctrl):
                kbd.press(Key.tab)
                kbd.release(Key.tab)
            
            return ToolResult(status="ok", output="Navigated to next chat.")
        except Exception as e:
            return ToolResult(status="error", output="", error=f"Failed to navigate: {e}")


class WhatsAppPreviousChatTool(BaseTool):
    """Navigate to the previous chat in WhatsApp."""

    name = "whatsapp.previous_chat"
    description = "Navigate to the previous chat in WhatsApp chat list."
    category = ToolCategory.SYSTEM
    risk = RiskLevel.LOW
    timeout_s = 5
    parameters = {"type": "object", "properties": {}, "required": []}

    async def run(self, args: dict) -> ToolResult:
        return await self.execute(**args)

    async def execute(self, **kwargs: Any) -> ToolResult:
        try:
            from pynput.keyboard import Controller, Key
            kbd = Controller()
            
            # Navigate up in chat list (Ctrl+Shift+Tab)
            with kbd.pressed(Key.ctrl, Key.shift):
                kbd.press(Key.tab)
                kbd.release(Key.tab)
            
            return ToolResult(status="ok", output="Navigated to previous chat.")
        except Exception as e:
            return ToolResult(status="error", output="", error=f"Failed to navigate: {e}")


class WhatsAppMuteChatTool(BaseTool):
    """Mute the current WhatsApp chat."""

    name = "whatsapp.mute_chat"
    description = "Mute notifications for the current WhatsApp chat."
    category = ToolCategory.SYSTEM
    risk = RiskLevel.LOW
    timeout_s = 5
    parameters = {"type": "object", "properties": {}, "required": []}

    async def run(self, args: dict) -> ToolResult:
        return await self.execute(**args)

    async def execute(self, **kwargs: Any) -> ToolResult:
        try:
            from pynput.keyboard import Controller, Key
            kbd = Controller()
            
            # Mute chat (Ctrl+Shift+M)
            with kbd.pressed(Key.ctrl, Key.shift):
                kbd.press('m')
                kbd.release('m')
            
            return ToolResult(status="ok", output="Muted current chat.")
        except Exception as e:
            return ToolResult(status="error", output="", error=f"Failed to mute chat: {e}")


WHATSAPP_AUTOMATION_TOOLS: list[BaseTool] = [
    WhatsAppNewChatTool(),
    WhatsAppSearchChatTool(),
    WhatsAppNextChatTool(),
    WhatsAppPreviousChatTool(),
    WhatsAppMuteChatTool(),
]
