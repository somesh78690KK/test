"""T.A.R.O. - Model Context Protocol (MCP) Client (TASK-121).

ARCHITECTURE reference: section 18 (Self-Extension).
RULES reference: section 3, section 4.
TASKS: TASK-121.

Integrates external MCP servers into T.A.R.O.'s tool registry:
1. Discovers tools from MCP servers using standard JSON-RPC protocol (tools/list).
2. Wraps each remote tool as an MCPToolAdapter (subclass of BaseTool).
3. Assigns RiskLevel.MEDIUM by default (requiring explicit user confirmation).
4. Forwards tool calls to the MCP server via tools/call.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any, Callable

from core.log.setup import get_logger
from core.tools.base import BaseTool, RiskLevel, ToolCategory, ToolResult

logger = get_logger(__name__)


class MCPToolAdapter(BaseTool):
    """Adapts an external MCP tool definition into a native T.A.R.O. BaseTool."""

    def __init__(
        self,
        server_name: str,
        tool_name: str,
        description: str,
        parameters: dict[str, Any],
        call_handler: Callable[[str, dict[str, Any]], Any],
        risk: RiskLevel = RiskLevel.MEDIUM,
    ) -> None:
        self.server_name = server_name
        self.raw_tool_name = tool_name
        self.name = f"mcp.{server_name}.{tool_name}"
        self.description = f"[MCP: {server_name}] {description}"
        self.category = ToolCategory.SKILL
        self.risk = risk  # ARCHITECTURE: default MEDIUM risk
        self.parameters = parameters
        self.call_handler = call_handler
        self.timeout_s = 30

    async def run(self, args: dict[str, Any]) -> ToolResult:
        return await self.execute(**args)

    async def execute(self, **kwargs: Any) -> ToolResult:
        try:
            if asyncio.iscoroutinefunction(self.call_handler):
                res = await self.call_handler(self.raw_tool_name, kwargs)
            else:
                res = self.call_handler(self.raw_tool_name, kwargs)

            if isinstance(res, ToolResult):
                return res

            if isinstance(res, dict):
                content = res.get("content", [])
                text_parts = []
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "text":
                        text_parts.append(item.get("text", ""))
                    elif isinstance(item, str):
                        text_parts.append(item)
                out_str = "\n".join(text_parts) if text_parts else str(res.get("output", res))
                is_error = res.get("isError", False)
                if is_error:
                    return ToolResult(status="error", output="", error=out_str)
                return ToolResult(status="ok", output=out_str)

            return ToolResult(status="ok", output=str(res))
        except Exception as e:
            logger.error("mcp_tool_execution_error", tool=self.name, error=str(e))
            return ToolResult(status="error", output="", error=f"MCP tool '{self.name}' failed: {e}")


class MCPClient:
    """Manages connection and tool registration from an external MCP server."""

    def __init__(self, server_name: str, transport: Any = None) -> None:
        self.server_name = server_name
        self.transport = transport
        self.registered_tools: list[MCPToolAdapter] = []

    async def list_tools(self) -> list[dict[str, Any]]:
        """Query MCP server for its advertised tools."""
        if self.transport is None:
            return []

        # If transport has direct list_tools method
        if hasattr(self.transport, "list_tools"):
            if asyncio.iscoroutinefunction(self.transport.list_tools):
                return await self.transport.list_tools()
            return self.transport.list_tools()

        # JSON-RPC tools/list request
        request = {
            "jsonrpc": "2.0",
            "id": str(uuid.uuid4()),
            "method": "tools/list",
            "params": {},
        }
        response = await self._send_request(request)
        return response.get("result", {}).get("tools", [])

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Send tools/call request to MCP server."""
        if hasattr(self.transport, "call_tool"):
            if asyncio.iscoroutinefunction(self.transport.call_tool):
                return await self.transport.call_tool(tool_name, arguments)
            return self.transport.call_tool(tool_name, arguments)

        request = {
            "jsonrpc": "2.0",
            "id": str(uuid.uuid4()),
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments,
            },
        }
        response = await self._send_request(request)
        return response.get("result", {})

    async def _send_request(self, request: dict[str, Any]) -> dict[str, Any]:
        if hasattr(self.transport, "send"):
            if asyncio.iscoroutinefunction(self.transport.send):
                return await self.transport.send(request)
            return self.transport.send(request)
        return {"result": {}}

    async def register_tools(self, registry: Any) -> list[MCPToolAdapter]:
        """Discover tools from the MCP server and register them in T.A.R.O.'s registry."""
        tools_specs = await self.list_tools()
        adapters: list[MCPToolAdapter] = []

        for spec in tools_specs:
            t_name = spec.get("name", "unnamed")
            t_desc = spec.get("description", "")
            t_params = spec.get("inputSchema", {"type": "object", "properties": {}})

            adapter = MCPToolAdapter(
                server_name=self.server_name,
                tool_name=t_name,
                description=t_desc,
                parameters=t_params,
                call_handler=self.call_tool,
                risk=RiskLevel.MEDIUM,
            )
            registry.register(adapter)
            adapters.append(adapter)
            logger.info("mcp_tool_registered", name=adapter.name, server=self.server_name)

        self.registered_tools = adapters
        return adapters
