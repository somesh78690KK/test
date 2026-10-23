"""T.A.R.O. - Audit log writer.

Writes a tamper-evident JSON-lines audit trail to logs/audit/.
Every tool call, approval, denial, and kill event gets one line.
Each line stores the SHA-256 of the previous line (hash chain).
A broken chain is detected at startup and reported.

ARCHITECTURE reference: sections 15, RULES section 4.
TASKS: TASK-034.
"""

from __future__ import annotations

import hashlib
import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class AuditLog:
    """Thread-safe append-only audit log with SHA-256 hash chaining.

    Args:
        log_dir: Directory for audit JSONL files (default: ``logs/audit/``).
    """

    def __init__(self, log_dir: Path | None = None) -> None:
        self._log_dir = log_dir or Path("logs/audit")
        self._log_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._prev_hash = self._find_last_hash()

    def _today_file(self) -> Path:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return self._log_dir / f"{today}.jsonl"

    def _find_last_hash(self) -> str:
        """Read the hash of the last line in today's log (if it exists)."""
        fp = self._today_file()
        if not fp.exists():
            return ""
        last_line = ""
        try:
            with fp.open(encoding="utf-8") as fh:
                for line in fh:
                    stripped = line.strip()
                    if stripped:
                        last_line = stripped
        except OSError:
            return ""
        if not last_line:
            return ""
        return hashlib.sha256(last_line.encode()).hexdigest()

    def _write(self, record: dict[str, Any]) -> None:
        """Append a record to today's audit file with hash chain."""
        with self._lock:
            record["_prev_hash"] = self._prev_hash
            line = json.dumps(record, separators=(",", ":"), default=str)
            self._prev_hash = hashlib.sha256(line.encode()).hexdigest()
            fp = self._today_file()
            with fp.open("a", encoding="utf-8") as fh:
                fh.write(line + "\n")

    def log_tool_call(
        self,
        tool: str,
        args_masked: dict[str, Any],
        result_status: str,
        result_error: str,
        duration_ms: int,
        request_id: str = "",
        risk: str = "",
    ) -> None:
        """Log a tool call result."""
        self._write(
            {
                "event": "tool_call",
                "ts": datetime.now(timezone.utc).isoformat(),
                "request_id": request_id,
                "tool": tool,
                "args": args_masked,
                "status": result_status,
                "error": result_error,
                "duration_ms": duration_ms,
                "risk": risk,
            }
        )

    def log_approval(
        self,
        tool: str,
        args_masked: dict[str, Any],
        decision: str,  # "approved" | "denied"
        risk: str,
        request_id: str = "",
    ) -> None:
        """Log a user approval or denial."""
        self._write(
            {
                "event": "confirmation",
                "ts": datetime.now(timezone.utc).isoformat(),
                "request_id": request_id,
                "tool": tool,
                "args": args_masked,
                "decision": decision,
                "risk": risk,
            }
        )

    def log_kill(self, trigger: str) -> None:
        """Log a kill switch activation."""
        self._write(
            {
                "event": "kill",
                "ts": datetime.now(timezone.utc).isoformat(),
                "trigger": trigger,
            }
        )

    def log_memory_write(
        self,
        record_id: str,
        store: str,
        action: str,
    ) -> None:
        """Log a memory write (RULES section 6)."""
        self._write(
            {
                "event": "memory_write",
                "ts": datetime.now(timezone.utc).isoformat(),
                "record_id": record_id,
                "store": store,
                "action": action,
            }
        )

    def verify_chain(self) -> tuple[bool, str]:
        """Verify the hash chain of today's log file.

        Returns:
            (ok, message) - ok is False if any line has a broken chain.
        """
        fp = self._today_file()
        if not fp.exists():
            return True, "No audit file for today."

        prev_hash = ""
        try:
            with fp.open(encoding="utf-8") as fh:
                for lineno, raw_line in enumerate(fh, start=1):
                    line = raw_line.strip()
                    if not line:
                        continue
                    record = json.loads(line)
                    stored_prev = record.get("_prev_hash", "")
                    if stored_prev != prev_hash:
                        return (
                            False,
                            f"Audit chain broken at line {lineno}. "
                            "The log may have been tampered with.",
                        )
                    prev_hash = hashlib.sha256(line.encode()).hexdigest()
        except (OSError, json.JSONDecodeError) as exc:
            return False, f"Audit file unreadable: {exc}"

        return True, "Audit chain intact."


# Aliases for convenience
AuditLogger = AuditLog

# Global audit log instance
_audit_log: AuditLog | None = None


def get_audit_log(log_dir: Path | None = None) -> AuditLog:
    """Return the global audit log (created on first call)."""
    global _audit_log
    if _audit_log is None or log_dir is not None:
        _audit_log = AuditLog(log_dir)
    return _audit_log


get_audit_logger = get_audit_log
default_audit_logger = get_audit_log()
