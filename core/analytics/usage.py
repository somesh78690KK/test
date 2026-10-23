"""T.A.R.O. - Local Usage Analytics (TASK-144).

ARCHITECTURE reference: section 14, section 26.
RULES reference: section 1 (Zero Cloud / Local Only), section 4.
TASKS: TASK-144.

Capabilities:
- Strictly local tracking of tool executions, successes, and failures.
- Zero outbound telemetry or cloud syncing.
- Computes aggregated metrics: tool counts, duration statistics, and failure rates.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from core.log.setup import get_logger

logger = get_logger(__name__)


@dataclass
class ToolStat:
    calls: int = 0
    successes: int = 0
    failures: int = 0
    total_duration_s: float = 0.0

    @property
    def failure_rate(self) -> float:
        if self.calls == 0:
            return 0.0
        return round((self.failures / self.calls) * 100.0, 2)

    @property
    def avg_duration_s(self) -> float:
        if self.calls == 0:
            return 0.0
        return round(self.total_duration_s / self.calls, 3)


class UsageAnalytics:
    """Collects and reports local usage statistics."""

    def __init__(self, storage_path: Path | None = None) -> None:
        if storage_path is None:
            repo_root = Path(__file__).resolve().parent.parent.parent
            self.storage_path = repo_root / "data" / "analytics.json"
        else:
            self.storage_path = storage_path

        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self.stats: dict[str, ToolStat] = {}
        self.total_sessions: int = 0
        self._load()

    def _load(self) -> None:
        if not self.storage_path.exists():
            return
        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.total_sessions = data.get("total_sessions", 0)
            raw_tools = data.get("tools", {})
            for name, s in raw_tools.items():
                self.stats[name] = ToolStat(
                    calls=s.get("calls", 0),
                    successes=s.get("successes", 0),
                    failures=s.get("failures", 0),
                    total_duration_s=s.get("total_duration_s", 0.0),
                )
        except Exception as e:
            logger.error("analytics_load_error", error=str(e))

    def _save(self) -> None:
        try:
            data = {
                "total_sessions": self.total_sessions,
                "tools": {name: asdict(stat) for name, stat in self.stats.items()},
                "last_updated": time.time(),
            }
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error("analytics_save_error", error=str(e))

    def record_tool_call(self, tool_name: str, success: bool, duration_s: float = 0.0) -> None:
        """Records an individual tool execution outcome."""
        if tool_name not in self.stats:
            self.stats[tool_name] = ToolStat()

        stat = self.stats[tool_name]
        stat.calls += 1
        if success:
            stat.successes += 1
        else:
            stat.failures += 1
        stat.total_duration_s += duration_s

        self._save()

    def get_report(self) -> dict[str, Any]:
        """Generates a summary report of tool counts and failure rates."""
        total_calls = sum(s.calls for s in self.stats.values())
        total_failures = sum(s.failures for s in self.stats.values())
        overall_failure_rate = round((total_failures / total_calls * 100.0), 2) if total_calls > 0 else 0.0

        tool_breakdown = {}
        for name, stat in sorted(self.stats.items(), key=lambda kv: kv[1].calls, reverse=True):
            tool_breakdown[name] = {
                "calls": stat.calls,
                "successes": stat.successes,
                "failures": stat.failures,
                "failure_rate_pct": stat.failure_rate,
                "avg_duration_s": stat.avg_duration_s,
            }

        return {
            "total_calls": total_calls,
            "total_failures": total_failures,
            "overall_failure_rate_pct": overall_failure_rate,
            "tools": tool_breakdown,
        }
