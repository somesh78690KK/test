"""T.A.R.O. - Shell Templates (PowerShell & CMD) (TASK-136).

ARCHITECTURE reference: section 14 (Code Execution & Sandbox), section 26.
RULES reference: section 4, 10.
TASKS: TASK-136.

Capabilities:
- Parametrized PowerShell and CMD shell templates.
- Strict parameter sanitization (blocks command injection chars ; & | ` $()).
- Sandboxed execution: working directory is strictly confined to `sandbox/`.
- Safe timeouts and kill-switch integration.
"""

from __future__ import annotations

import os
import re
import subprocess
import time
from pathlib import Path
from typing import Any

from core.log.setup import get_logger
from core.safety.kill_switch import kill_switch
from core.safety.sandbox import DEFAULT_SANDBOX_TIMEOUT, CodeSandbox
from core.tools.base import BaseTool, RiskLevel, ToolCategory, ToolResult

logger = get_logger(__name__)

# Injection patterns prohibited in shell parameters
INJECTION_PATTERN = re.compile(r"[;&|`$<>^!\n\r]")

SHELL_TEMPLATES: dict[str, dict[str, Any]] = {
    "list_files": {
        "shell": "powershell",
        "description": "List files in the sandbox matching a filter.",
        "template": "Get-ChildItem -Path . -Filter '{filter}' -Recurse | Select-Object -First {limit} Name, Length, LastWriteTime | Format-Table -AutoSize",
        "defaults": {"filter": "*", "limit": 50},
        "allowed_params": ["filter", "limit"],
    },
    "file_hash": {
        "shell": "powershell",
        "description": "Calculate SHA256 hash of a file inside the sandbox.",
        "template": "Get-FileHash -Path '{filename}' -Algorithm SHA256 | Select-Object Algorithm, Hash, Path",
        "defaults": {"filename": ""},
        "allowed_params": ["filename"],
    },
    "count_lines": {
        "shell": "powershell",
        "description": "Count total lines in a sandbox text file.",
        "template": "(Get-Content -Path '{filename}' | Measure-Object -Line).Lines",
        "defaults": {"filename": ""},
        "allowed_params": ["filename"],
    },
    "cmd_dir": {
        "shell": "cmd",
        "description": "Run standard CMD dir command in sandbox.",
        "template": "dir /b {options}",
        "defaults": {"options": ""},
        "allowed_params": ["options"],
    },
    "cmd_type": {
        "shell": "cmd",
        "description": "Read file contents via CMD in sandbox.",
        "template": "type {filename}",
        "defaults": {"filename": ""},
        "allowed_params": ["filename"],
    },
}


class ShellTemplateTool(BaseTool):
    """Executes validated shell templates strictly inside the sandbox environment."""

    name = "coding.shell_template"
    description = (
        "Execute a predefined, parametrized PowerShell or CMD template strictly inside the sandbox directory."
    )
    category = ToolCategory.CODING
    risk = RiskLevel.MEDIUM
    timeout_s = 30
    parameters = {
        "type": "object",
        "properties": {
            "template_name": {
                "type": "string",
                "enum": list(SHELL_TEMPLATES.keys()),
                "description": "Name of the shell template to run.",
            },
            "parameters": {
                "type": "object",
                "description": "Key-value arguments to interpolate into the template.",
            },
            "timeout_s": {
                "type": "number",
                "description": "Max execution duration in seconds (default: 15s).",
            },
        },
        "required": ["template_name"],
    }

    def __init__(self, sandbox_dir: Path | None = None) -> None:
        super().__init__()
        self.sandbox = CodeSandbox(sandbox_dir=sandbox_dir)
        self.sandbox_dir = self.sandbox.sandbox_dir

    async def run(self, args: dict[str, Any]) -> ToolResult:
        return await self.execute(**args)

    async def execute(self, **kwargs: Any) -> ToolResult:
        template_name = kwargs.get("template_name", "")
        params = kwargs.get("parameters", {})
        timeout_s = float(kwargs.get("timeout_s", 15.0))

        if kill_switch.is_killed:
            return ToolResult.error_result("Execution blocked: Global kill switch is active.")

        if template_name not in SHELL_TEMPLATES:
            return ToolResult.error_result(
                f"Unknown shell template '{template_name}'. Available: {list(SHELL_TEMPLATES.keys())}"
            )

        spec = SHELL_TEMPLATES[template_name]
        template_str = spec["template"]
        shell_type = spec["shell"]
        defaults = spec.get("defaults", {})
        allowed = spec.get("allowed_params", [])

        # Validate and sanitize parameters
        merged_params = dict(defaults)
        if isinstance(params, dict):
            for k, v in params.items():
                if k not in allowed:
                    return ToolResult.error_result(f"Disallowed parameter '{k}' for template '{template_name}'.")

                v_str = str(v)
                # Check for command injection characters
                if INJECTION_PATTERN.search(v_str):
                    return ToolResult.error_result(
                        f"Security violation: Parameter '{k}' contains prohibited shell metacharacters."
                    )
                # Check for path traversal outside sandbox
                if ".." in v_str or (os.path.isabs(v_str) and not str(Path(v_str).resolve()).startswith(str(self.sandbox_dir))):
                    return ToolResult.error_result(
                        f"Security violation: Parameter '{k}' attempts path traversal outside sandbox."
                    )

                merged_params[k] = v_str

        # Format command
        try:
            rendered_cmd = template_str.format(**merged_params)
        except Exception as e:
            return ToolResult.error_result(f"Failed to render template: {e}")

        logger.info(
            "shell_template_executing",
            template=template_name,
            shell=shell_type,
            cwd=str(self.sandbox_dir),
        )

        # Prepare invocation
        if shell_type == "powershell":
            cmd_args = [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                rendered_cmd,
            ]
        else:
            cmd_args = ["cmd.exe", "/c", rendered_cmd]

        start_time = time.monotonic()
        try:
            proc = subprocess.run(
                cmd_args,
                cwd=str(self.sandbox_dir),
                capture_output=True,
                text=True,
                timeout=timeout_s,
            )
            duration = round(time.monotonic() - start_time, 2)

            if proc.returncode != 0:
                return ToolResult(
                    status="error",
                    output=proc.stdout.strip(),
                    error=proc.stderr.strip() or f"Command exited with return code {proc.returncode}",
                    data={"duration_s": duration, "returncode": proc.returncode},
                )

            return ToolResult.ok(
                proc.stdout.strip() or "[Command completed successfully with no output]",
                data={"duration_s": duration, "returncode": proc.returncode},
            )

        except subprocess.TimeoutExpired:
            return ToolResult.error_result(f"Shell template execution timed out after {timeout_s}s.")
        except Exception as e:
            return ToolResult.error_result(f"Failed to execute shell template: {e}")
