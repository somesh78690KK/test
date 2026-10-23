"""T.A.R.O. - Coding sandbox tool.

ARCHITECTURE reference: section 14.
RULES reference: section 4, 10.
TASKS: TASK-035.

Tool exposing Python execution inside the secure sandbox directory with
fixed cwd, timeout, and output capture.
"""

from __future__ import annotations

from typing import Any

from core.safety.sandbox import default_sandbox
from core.tools.base import BaseTool, RiskLevel, ToolCategory, ToolResult


class RunPythonTool(BaseTool):
    """Executes Python code in the sandbox."""

    name = "code.run_python"
    description = "Execute Python code inside the sandbox with timeout and output capture."
    category = ToolCategory.CODING
    risk = RiskLevel.MEDIUM
    timeout_s = 35
    parameters = {
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": "Python code to execute.",
            },
            "timeout_s": {
                "type": "number",
                "description": "Execution timeout in seconds (default 30).",
            },
        },
        "required": ["code"],
    }

    async def run(self, args: dict) -> ToolResult:
        return await self.execute(**args)

    async def execute(self, **kwargs: Any) -> ToolResult:
        code = kwargs.get("code")
        if not code:
            return ToolResult(status="error", output="", error="Missing 'code' argument.")

        timeout = float(kwargs.get("timeout_s", 30.0))
        result = default_sandbox.execute_python(code, timeout_s=timeout)

        if not result.success:
            err = result.blocked_reason or result.stderr
            return ToolResult(
                status="error",
                output=result.stdout,
                error=err,
            )

        output = result.stdout
        if not output.strip():
            output = f"[Execution finished with return code {result.returncode} and no stdout]"

        return ToolResult(status="ok", output=output)


CODING_TOOLS: list[BaseTool] = [
    RunPythonTool(),
]
