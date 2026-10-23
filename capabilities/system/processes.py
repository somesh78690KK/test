"""T.A.R.O. - Process management and termination.

ARCHITECTURE reference: section 14.
RULES reference: section 4, 10.
TASKS: TASK-042.

Tools for listing running processes and safely terminating processes with
HIGH risk classification and refusal for critical system processes.
"""

from __future__ import annotations

import os
import signal
from typing import Any

from core.log.setup import get_logger
from core.tools.base import BaseTool, RiskLevel, ToolCategory, ToolResult

logger = get_logger(__name__)

# System and protected processes that must NEVER be terminated
PROTECTED_PROCESS_NAMES = {
    "system",
    "system idle process",
    "smss.exe",
    "csrss.exe",
    "wininit.exe",
    "services.exe",
    "lsass.exe",
    "lsm.exe",
    "winlogon.exe",
    "svchost.exe",
    "spoolsv.exe",
    "explorer.exe",
    "dwmapi.exe",
    "fontdrvhost.exe",
}


class ProcessListTool(BaseTool):
    """Lists currently running processes."""

    name = "process.list"
    description = "List currently running processes with PID, name, and memory."
    category = ToolCategory.SYSTEM
    risk = RiskLevel.SAFE
    timeout_s = 15
    parameters = {
        "type": "object",
        "properties": {
            "filter_name": {
                "type": "string",
                "description": "Optional substring filter for process name.",
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum number of processes to return (default 50).",
            },
        },
    }

    async def run(self, args: dict) -> ToolResult:
        return await self.execute(**args)

    async def execute(self, **kwargs: Any) -> ToolResult:
        filter_name = kwargs.get("filter_name", "").strip().lower()
        max_results = kwargs.get("max_results", 50)

        try:
            import psutil

            procs = []
            for p in psutil.process_iter(["pid", "name", "memory_info"]):
                try:
                    info = p.info
                    pname = str(info.get("name") or "")
                    if filter_name and filter_name not in pname.lower():
                        continue
                    mem = info.get("memory_info")
                    mem_mb = (mem.rss / (1024 * 1024)) if mem else 0.0
                    procs.append((info["pid"], pname, mem_mb))
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            # Sort by memory descending
            procs.sort(key=lambda x: x[2], reverse=True)
            subset = procs[:max_results]

            lines = [f"{'PID':>8}  {'Process Name':<30}  {'Memory (MB)':>12}"]
            lines.append("-" * 54)
            for pid, name, mem_mb in subset:
                lines.append(f"{pid:>8}  {name:<30}  {mem_mb:>11.1f} MB")

            return ToolResult(
                status="ok",
                output=f"Running processes ({len(subset)} of {len(procs)}):\n" + "\n".join(lines),
            )
        except Exception as e:
            logger.error("process_list_error", error=str(e))
            return ToolResult(status="error", output="", error=f"Failed to list processes: {e}")


class ProcessTerminateTool(BaseTool):
    """Terminates a process by PID or name (HIGH risk). Refuses protected processes."""

    name = "process.terminate"
    description = "Terminate a running process by PID or name (HIGH risk). Protected system processes cannot be terminated."
    category = ToolCategory.SYSTEM
    risk = RiskLevel.HIGH
    timeout_s = 15
    parameters = {
        "type": "object",
        "properties": {
            "pid": {"type": "integer", "description": "Process ID to terminate."},
            "name": {"type": "string", "description": "Process name to terminate (e.g. 'notepad.exe')."},
        },
    }

    async def run(self, args: dict) -> ToolResult:
        return await self.execute(**args)

    async def execute(self, **kwargs: Any) -> ToolResult:
        pid = kwargs.get("pid")
        proc_name = kwargs.get("name")

        if not pid and not proc_name:
            return ToolResult(
                status="error",
                output="",
                error="Either 'pid' or 'name' must be provided to terminate a process.",
            )

        if proc_name and proc_name.strip().lower() in PROTECTED_PROCESS_NAMES:
            p_name = proc_name.strip().lower()
            logger.warning("protected_process_termination_refused", name=p_name)
            return ToolResult(
                status="error",
                output="",
                error=f"Refused: '{p_name}' is a protected system process and cannot be terminated.",
            )

        try:
            import psutil

            target_procs: list[psutil.Process] = []
            if pid:
                try:
                    target_procs.append(psutil.Process(pid))
                except psutil.NoSuchProcess:
                    return ToolResult(status="error", output="", error=f"Process with PID {pid} not found.")
            elif proc_name:
                name_clean = proc_name.strip().lower()
                for p in psutil.process_iter(["pid", "name"]):
                    try:
                        if (p.info["name"] or "").lower() == name_clean:
                            target_procs.append(p)
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass

                if not target_procs:
                    return ToolResult(
                        status="error",
                        output="",
                        error=f"No running processes found matching name '{proc_name}'.",
                    )

            # Check for protected processes
            terminated = []
            for p in target_procs:
                p_name = p.name().lower()
                if p_name in PROTECTED_PROCESS_NAMES or p.pid in (0, 4):
                    logger.warning("protected_process_termination_refused", pid=p.pid, name=p_name)
                    return ToolResult(
                        status="error",
                        output="",
                        error=f"Refused: '{p_name}' (PID {p.pid}) is a protected system process and cannot be terminated.",
                    )

                p.terminate()
                terminated.append(f"{p_name} (PID: {p.pid})")

            return ToolResult(
                status="ok",
                output=f"Successfully terminated: {', '.join(terminated)}.",
            )
        except Exception as e:
            logger.error("process_terminate_error", error=str(e))
            return ToolResult(status="error", output="", error=f"Failed to terminate process: {e}")


PROCESS_TOOLS: list[BaseTool] = [
    ProcessListTool(),
    ProcessTerminateTool(),
]
