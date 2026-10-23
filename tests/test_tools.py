"""T.A.R.O. - Tool registry and validation tests.

TASKS: TASK-020.
Acceptance test: Tool missing risk or timeout fails registration.
"""

from __future__ import annotations

from typing import Any

import pytest
from core.tools.base import BaseTool, RiskLevel, ToolCategory, ToolResult
from core.tools.registry import ToolRegistry


class ValidTool(BaseTool):
    name = "test.valid"
    description = "A valid test tool"
    category = ToolCategory.SYSTEM
    risk = RiskLevel.SAFE
    timeout_s = 10
    parameters = {"type": "object", "properties": {}}

    async def run(self, args: dict[str, Any]) -> ToolResult:
        return ToolResult(status="ok", output="done")


def test_valid_tool_registration() -> None:
    """Verifies that a well-defined tool registers cleanly."""
    registry = ToolRegistry()
    tool = ValidTool()
    registry.register(tool)
    assert registry.get("test.valid") is tool
    assert len(registry.all_tools()) == 1


def test_tool_missing_risk_fails_registration() -> None:
    """TASK-020 acceptance: Tool missing risk fails registration."""
    class MissingRiskTool(BaseTool):
        name = "test.no_risk"
        description = "No risk declared"
        category = ToolCategory.FILES
        risk = None  # type: ignore[assignment]
        timeout_s = 10
        parameters = {"type": "object", "properties": {}}

        async def run(self, args: dict[str, Any]) -> ToolResult:
            return ToolResult(status="ok")

    registry = ToolRegistry()
    with pytest.raises(ValueError) as exc:
        registry.register(MissingRiskTool())
    assert "missing required attribute 'risk'" in str(exc.value)


def test_tool_missing_timeout_fails_registration() -> None:
    """TASK-020 acceptance: Tool missing timeout fails registration."""
    class MissingTimeoutTool(BaseTool):
        name = "test.no_timeout"
        description = "No timeout declared"
        category = ToolCategory.FILES
        risk = RiskLevel.LOW
        timeout_s = None  # type: ignore[assignment]
        parameters = {"type": "object", "properties": {}}

        async def run(self, args: dict[str, Any]) -> ToolResult:
            return ToolResult(status="ok")

    registry = ToolRegistry()
    with pytest.raises(ValueError) as exc:
        registry.register(MissingTimeoutTool())
    assert "missing required attribute 'timeout_s'" in str(exc.value)
