"""T.A.R.O. - Security Guardian Service (TASK-137).

ARCHITECTURE reference: section 14 (System Control & Security), section 26.
RULES reference: section 3, 4, 10.
TASKS: TASK-137.

Capabilities:
- Proactive process security monitor (off by default).
- Flags processes executing from untrusted locations (e.g. %TEMP%, AppData/Local/Temp).
- Quarantine operation: HIGH risk, requires user confirmation before terminating
  and isolating the suspicious executable.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from core.log.setup import get_logger
from core.tools.base import BaseTool, RiskLevel, ToolCategory, ToolResult

logger = get_logger(__name__)


@dataclass
class SuspiciousProcess:
    pid: int
    name: str
    exe_path: str
    reason: str
    flagged_at: float


class SecurityGuardian:
    """Security Guardian background monitor."""

    def __init__(self, enabled: bool = False, quarantine_dir: Path | None = None) -> None:
        self.enabled = enabled
        if quarantine_dir is None:
            repo_root = Path(__file__).resolve().parent.parent.parent
            self.quarantine_dir = repo_root / "data" / "quarantine"
        else:
            self.quarantine_dir = quarantine_dir

        self.quarantine_dir.mkdir(parents=True, exist_ok=True)
        self.flagged_processes: list[SuspiciousProcess] = []

    def scan_processes(self, process_list: list[dict[str, Any]] | None = None) -> list[SuspiciousProcess]:
        """Scans running processes and flags any running from temporary/untrusted directories."""
        flagged: list[SuspiciousProcess] = []
        temp_dir = tempfile.gettempdir().lower()

        # If a mock/explicit process list was provided (e.g. in tests)
        if process_list is not None:
            for p in process_list:
                exe = str(p.get("exe") or "").lower()
                pid = int(p.get("pid", 0))
                name = str(p.get("name", "unknown"))

                if temp_dir in exe or "appdata\\local\\temp" in exe or "/tmp" in exe:
                    sp = SuspiciousProcess(
                        pid=pid,
                        name=name,
                        exe_path=p.get("exe", ""),
                        reason=f"Process is executing from temporary directory: {exe}",
                        flagged_at=float(p.get("time", 0.0)),
                    )
                    flagged.append(sp)
            self.flagged_processes = flagged
            return flagged

        # Real process scanning using psutil
        try:
            import psutil
            for proc in psutil.process_iter(["pid", "name", "exe"]):
                try:
                    info = proc.info
                    exe = str(info.get("exe") or "").lower()
                    if not exe:
                        continue
                    if temp_dir in exe or "appdata\\local\\temp" in exe:
                        sp = SuspiciousProcess(
                            pid=info["pid"],
                            name=info.get("name", ""),
                            exe_path=info.get("exe", ""),
                            reason=f"Process executing from temporary directory: {exe}",
                            flagged_at=0.0,
                        )
                        flagged.append(sp)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except ImportError:
            logger.debug("psutil_not_available_for_security_guardian")

        self.flagged_processes = flagged
        return flagged

    def quarantine(self, pid: int, confirmed: bool = False) -> dict[str, Any]:
        """Terminates and isolates the suspicious process executable.

        CRITICAL: Requires confirmation before execution.
        """
        if not confirmed:
            return {
                "success": False,
                "needs_confirmation": True,
                "message": f"Quarantine of PID {pid} requires explicit confirmation.",
            }

        target = next((p for p in self.flagged_processes if p.pid == pid), None)
        if not target:
            return {"success": False, "message": f"PID {pid} not found in flagged processes."}

        # Attempt to kill process
        try:
            import psutil
            p = psutil.Process(target.pid)
            p.terminate()
            p.wait(timeout=3)
        except Exception as e:
            logger.warning("process_kill_warning", pid=target.pid, error=str(e))

        # Quarantine binary
        target_path = Path(target.exe_path)
        quarantined_path = self.quarantine_dir / f"{target.name}_{target.pid}.quarantine"
        try:
            if target_path.exists():
                shutil.move(str(target_path), str(quarantined_path))
        except Exception as e:
            logger.error("quarantine_file_move_failed", error=str(e))

        logger.info("process_quarantined", pid=pid, name=target.name)
        return {
            "success": True,
            "pid": target.pid,
            "name": target.name,
            "quarantined_to": str(quarantined_path),
            "message": f"Successfully quarantined process '{target.name}' (PID {target.pid}).",
        }


class SecurityGuardianTool(BaseTool):
    """Tool to inspect flagged processes and quarantine threats."""

    name = "security.guardian"
    description = (
        "Security Guardian service: scan for suspicious processes in temp directories "
        "and quarantine confirmed threats."
    )
    category = ToolCategory.SYSTEM
    risk = RiskLevel.HIGH
    timeout_s = 20
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["scan", "status", "quarantine"],
                "description": "Security action to perform.",
            },
            "pid": {"type": "integer", "description": "Process ID to quarantine."},
            "confirmed": {"type": "boolean", "description": "User confirmation for quarantine."},
        },
        "required": ["action"],
    }

    def __init__(self, guardian: SecurityGuardian | None = None) -> None:
        super().__init__()
        self.guardian = guardian or SecurityGuardian()

    async def run(self, args: dict[str, Any]) -> ToolResult:
        return await self.execute(**args)

    async def execute(self, **kwargs: Any) -> ToolResult:
        action = kwargs.get("action", "status")

        if action == "status":
            return ToolResult.ok(
                f"Security Guardian is {'ENABLED' if self.guardian.enabled else 'DISABLED (off by default)'}. "
                f"Flagged processes: {len(self.guardian.flagged_processes)}."
            )

        elif action == "scan":
            flagged = self.guardian.scan_processes()
            if not flagged:
                return ToolResult.ok("Scan complete: No suspicious processes detected.")
            lines = [f"Security Guardian flagged {len(flagged)} suspicious process(es):"]
            for sp in flagged:
                lines.append(f"- PID {sp.pid}: '{sp.name}' ({sp.exe_path}) - {sp.reason}")
            return ToolResult.ok("\n".join(lines), data=[vars(sp) for sp in flagged])

        elif action == "quarantine":
            pid = kwargs.get("pid")
            if pid is None:
                return ToolResult.error_result("Quarantine action requires a 'pid'.")
            confirmed = bool(kwargs.get("confirmed", False))
            res = self.guardian.quarantine(pid, confirmed=confirmed)
            if not res["success"]:
                return ToolResult.error_result(res["message"])
            return ToolResult.ok(res["message"], data=res)

        return ToolResult.error_result(f"Unknown Security Guardian action: '{action}'")
