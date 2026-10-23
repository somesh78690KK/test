"""T.A.R.O. - Application Memory and Behavior Skills.

Provides tools for storing and retrieving application usage patterns and behavior analysis.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.log.setup import get_logger
from core.tools.base import BaseTool, RiskLevel, ToolCategory, ToolResult

logger = get_logger(__name__)

MEMORY_PATH = Path("data/app_memory.json")


class AddApplicationToMemoryTool(BaseTool):
    """Add an application to memory with usage context."""

    name = "add_application_to_memory"
    description = "Store information about an application in memory for future reference."
    category = ToolCategory.SYSTEM
    risk = RiskLevel.LOW
    timeout_s = 5
    parameters = {
        "type": "object",
        "properties": {
            "app_name": {
                "type": "string",
                "description": "Name of the application.",
            },
            "context": {
                "type": "string",
                "description": "Usage context or purpose.",
            },
        },
        "required": ["app_name"],
    }
    parameters = {
        "type": "object",
        "properties": {
            "app_name": {
                "type": "string",
                "description": "Name of the application.",
            },
            "context": {
                "type": "string",
                "description": "Usage context or purpose.",
            },
        },
        "required": ["app_name"],
    }

    async def run(self, args: dict) -> ToolResult:
        return await self.execute(**args)

    async def execute(self, **kwargs: Any) -> ToolResult:
        app_name = kwargs.get("app_name", "").strip()
        context = kwargs.get("context", "").strip()
        
        if not app_name:
            return ToolResult(status="error", output="", error="Missing 'app_name' argument.")
        
        try:
            MEMORY_PATH.parent.mkdir(parents=True, exist_ok=True)
            
            if MEMORY_PATH.exists():
                with open(MEMORY_PATH, "r", encoding="utf-8") as f:
                    memory = json.load(f)
            else:
                memory = {}
            
            memory[app_name] = {
                "context": context,
                "last_used": str(Path.cwd())
            }
            
            with open(MEMORY_PATH, "w", encoding="utf-8") as f:
                json.dump(memory, f, indent=2)
            
            return ToolResult(status="ok", output=f"Added {app_name} to memory.")
        except Exception as e:
            return ToolResult(status="error", output="", error=f"Failed to add to memory: {e}")


class GetApplicationMemoryTool(BaseTool):
    """Retrieve information about an application from memory."""

    name = "get_application_memory"
    description = "Get stored information about an application from memory."
    category = ToolCategory.SYSTEM
    risk = RiskLevel.LOW
    timeout_s = 5
    parameters = {
        "type": "object",
        "properties": {
            "app_name": {
                "type": "string",
                "description": "Name of the application to retrieve.",
            },
        },
        "required": ["app_name"],
    }
    parameters = {
        "type": "object",
        "properties": {
            "app_name": {
                "type": "string",
                "description": "Name of the application to retrieve.",
            },
        },
        "required": ["app_name"],
    }

    async def run(self, args: dict) -> ToolResult:
        return await self.execute(**args)

    async def execute(self, **kwargs: Any) -> ToolResult:
        app_name = kwargs.get("app_name", "").strip()
        
        if not app_name:
            return ToolResult(status="error", output="", error="Missing 'app_name' argument.")
        
        try:
            if not MEMORY_PATH.exists():
                return ToolResult(status="ok", output="No application memory found.")
            
            with open(MEMORY_PATH, "r", encoding="utf-8") as f:
                memory = json.load(f)
            
            if app_name in memory:
                return ToolResult(status="ok", output=f"Memory for {app_name}: {memory[app_name]}")
            else:
                return ToolResult(status="ok", output=f"No memory found for {app_name}.")
        except Exception as e:
            return ToolResult(status="error", output="", error=f"Failed to retrieve memory: {e}")


class RemoveApplicationFromMemoryTool(BaseTool):
    """Remove an application from memory."""

    name = "remove_application_from_memory"
    description = "Remove an application from stored memory."
    category = ToolCategory.SYSTEM
    risk = RiskLevel.LOW
    timeout_s = 5
    parameters = {
        "type": "object",
        "properties": {
            "app_name": {
                "type": "string",
                "description": "Name of the application to remove.",
            },
        },
        "required": ["app_name"],
    }
    parameters = {
        "type": "object",
        "properties": {
            "app_name": {
                "type": "string",
                "description": "Name of the application to remove.",
            },
        },
        "required": ["app_name"],
    }

    async def run(self, args: dict) -> ToolResult:
        return await self.execute(**args)

    async def execute(self, **kwargs: Any) -> ToolResult:
        app_name = kwargs.get("app_name", "").strip()
        
        if not app_name:
            return ToolResult(status="error", output="", error="Missing 'app_name' argument.")
        
        try:
            if not MEMORY_PATH.exists():
                return ToolResult(status="ok", output="No application memory found.")
            
            with open(MEMORY_PATH, "r", encoding="utf-8") as f:
                memory = json.load(f)
            
            if app_name in memory:
                del memory[app_name]
                with open(MEMORY_PATH, "w", encoding="utf-8") as f:
                    json.dump(memory, f, indent=2)
                return ToolResult(status="ok", output=f"Removed {app_name} from memory.")
            else:
                return ToolResult(status="ok", output=f"{app_name} not in memory.")
        except Exception as e:
            return ToolResult(status="error", output="", error=f"Failed to remove from memory: {e}")


class AnalyzeBehaviorPatternsTool(BaseTool):
    """Analyze user behavior patterns from memory."""

    name = "analyze_behavior_patterns"
    description = "Analyze stored application usage patterns to understand user behavior."
    category = ToolCategory.SYSTEM
    risk = RiskLevel.LOW
    timeout_s = 10
    parameters = {"type": "object", "properties": {}, "required": []}

    async def run(self, args: dict) -> ToolResult:
        return await self.execute(**args)

    async def execute(self, **kwargs: Any) -> ToolResult:
        try:
            if not MEMORY_PATH.exists():
                return ToolResult(status="ok", output="No application memory found for analysis.")
            
            with open(MEMORY_PATH, "r", encoding="utf-8") as f:
                memory = json.load(f)
            
            pattern_summary = f"Found {len(memory)} applications in memory. "
            pattern_summary += "Behavior analysis available for further processing."
            
            return ToolResult(status="ok", output=pattern_summary)
        except Exception as e:
            return ToolResult(status="error", output="", error=f"Failed to analyze patterns: {e}")


class GetApplicationSummaryTool(BaseTool):
    """Get a summary of all applications in memory."""

    name = "get_application_summary"
    description = "Get a summary of all applications stored in memory."
    category = ToolCategory.SYSTEM
    risk = RiskLevel.LOW
    timeout_s = 5
    parameters = {"type": "object", "properties": {}, "required": []}

    async def run(self, args: dict) -> ToolResult:
        return await self.execute(**args)

    async def execute(self, **kwargs: Any) -> ToolResult:
        try:
            if not MEMORY_PATH.exists():
                return ToolResult(status="ok", output="No applications in memory.")
            
            with open(MEMORY_PATH, "r", encoding="utf-8") as f:
                memory = json.load(f)
            
            apps = list(memory.keys())
            return ToolResult(status="ok", output=f"Applications in memory: {', '.join(apps)}")
        except Exception as e:
            return ToolResult(status="error", output="", error=f"Failed to get summary: {e}")


APP_MEMORY_TOOLS: list[BaseTool] = [
    AddApplicationToMemoryTool(),
    GetApplicationMemoryTool(),
    RemoveApplicationFromMemoryTool(),
    AnalyzeBehaviorPatternsTool(),
    GetApplicationSummaryTool(),
]
