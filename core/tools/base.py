"""T.A.R.O. - Tool base class and ToolResult.

Every capability and skill exposes itself to the orchestrator as a subclass
of BaseTool. The registry validates that every required field is present
before the tool is registered.

ARCHITECTURE reference: section 7.1.
RULES reference: sections 3, 10.
TASKS: TASK-020.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

# ---------------------------------------------------------------------------
# Risk levels
# ---------------------------------------------------------------------------


class RiskLevel(str, Enum):
    """Ordered risk levels for tool calls.

    ARCHITECTURE section 8: risk comes from code, never from model output.
    """

    SAFE = "SAFE"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, RiskLevel):
            return NotImplemented
        order = list(RiskLevel)
        return order.index(self) < order.index(other)

    def __le__(self, other: object) -> bool:
        if not isinstance(other, RiskLevel):
            return NotImplemented
        return self == other or self < other

    def __gt__(self, other: object) -> bool:
        if not isinstance(other, RiskLevel):
            return NotImplemented
        return not self <= other

    def __ge__(self, other: object) -> bool:
        if not isinstance(other, RiskLevel):
            return NotImplemented
        return not self < other


# ---------------------------------------------------------------------------
# Tool categories
# ---------------------------------------------------------------------------


class ToolCategory(str, Enum):
    """Tool family categories, used for schema filtering per request."""

    SYSTEM = "system"
    FILES = "files"
    BROWSER = "browser"
    VISION = "vision"
    OFFICE = "office"
    HARDWARE = "hardware"
    TRAINING = "training"
    CLOUD = "cloud"
    SKILL = "skill"
    SHELL = "shell"
    UI_CONTROL = "ui_control"
    APP_INTEL = "app_intel"
    ANALYTICS = "analytics"
    DOCS_QA = "docs_qa"
    REMINDERS = "reminders"
    NOTES = "notes"
    CODING = "coding"
    GUARDIANS = "guardians"
    CORE = "core"  # Meta tools: find_tools, memory_save, etc.


# ---------------------------------------------------------------------------
# ToolResult
# ---------------------------------------------------------------------------


@dataclass
class ToolResult:
    """Structured result returned by every tool.

    RULES section 3: every tool returns a ToolResult with status, output,
    and error. Exceptions are caught and converted.
    """

    status: str  # "ok" | "error" | "denied" | "timeout" | "partial"
    output: str = ""
    error: str = ""
    duration_ms: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def ok(cls, output: str, duration_ms: int = 0, **meta: Any) -> "ToolResult":
        """Convenience constructor for a successful result."""
        return cls(status="ok", output=output, duration_ms=duration_ms, metadata=meta)

    @classmethod
    def error_result(cls, error: str, duration_ms: int = 0) -> "ToolResult":
        """Convenience constructor for an error result."""
        return cls(status="error", error=error, duration_ms=duration_ms)

    @classmethod
    def denied(cls, reason: str) -> "ToolResult":
        """Convenience constructor for a permission-denied result."""
        return cls(status="denied", error=reason)

    @classmethod
    def timeout_result(cls, tool_name: str, timeout_s: int) -> "ToolResult":
        """Convenience constructor for a timeout result."""
        return cls(
            status="timeout",
            error=f"{tool_name} exceeded its {timeout_s}s timeout.",
        )

    def to_status_line(self, name: str) -> str:
        """Format a one-line status block entry, e.g. ``file.copy: OK``."""
        if self.status == "ok":
            suffix = f" ({self.duration_ms}ms)" if self.duration_ms else ""
            return f"{name}: OK{suffix}"
        if self.status == "denied":
            return f"{name}: DENIED - {self.error}"
        if self.status == "timeout":
            return f"{name}: TIMEOUT - {self.error}"
        return f"{name}: FAILED - {self.error}"


# ---------------------------------------------------------------------------
# ToolError exception
# ---------------------------------------------------------------------------


class ToolError(Exception):
    """Raised inside a tool when a recoverable error occurs.

    The registry catches this and converts it to a ToolResult.error_result.
    """


# ---------------------------------------------------------------------------
# Base tool
# ---------------------------------------------------------------------------


class BaseTool(ABC):
    """Abstract base for all T.A.R.O. tools.

    Subclasses must set ``name``, ``description``, ``parameters``,
    ``risk``, ``category``, and ``timeout_s``. The registry enforces this.

    The ``run()`` method must:
    - Return a ToolResult (never raise an unhandled exception).
    - Never report ok status when the action partially failed.
    """

    # Required class attributes - registry validates these exist
    name: str
    description: str
    parameters: dict  # JSON schema for inputs
    risk: RiskLevel
    category: ToolCategory
    timeout_s: int

    def to_schema(self) -> dict:
        """Return the JSON schema representation for the Ollama tools list."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    @abstractmethod
    async def run(self, args: dict) -> ToolResult:
        """Execute the tool.

        Args:
            args: Validated arguments from the model.

        Returns:
            ToolResult with status, output, and error.
        """
        ...

    async def safe_run(self, args: dict) -> ToolResult:
        """Execute run() and catch any unhandled exceptions.

        Returns a ToolResult.error_result on unexpected exceptions.
        Wraps the call with a timer.
        """
        start = time.monotonic()
        try:
            result = await self.run(args)
            result.duration_ms = int((time.monotonic() - start) * 1000)
            return result
        except ToolError as exc:
            return ToolResult.error_result(
                str(exc),
                duration_ms=int((time.monotonic() - start) * 1000),
            )
        except Exception as exc:  # noqa: BLE001 - must not surface raw exceptions
            return ToolResult.error_result(
                f"Unexpected error in {self.name}: {type(exc).__name__}: {exc}",
                duration_ms=int((time.monotonic() - start) * 1000),
            )
