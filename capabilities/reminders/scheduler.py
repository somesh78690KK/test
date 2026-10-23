"""T.A.R.O. - Workflow Scheduler (TASK-139).

ARCHITECTURE reference: section 14 (Reminders & Workflows), section 26.
RULES reference: section 3, 4, 10.
TASKS: TASK-139.

Capabilities:
- Persistent cron/interval workflow scheduler.
- Schedules persist across application restarts in JSON storage.
- CRITICAL SAFETY: HIGH-risk workflows or actions are strictly refused from automated scheduling.
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable

from core.log.setup import get_logger
from core.tools.base import BaseTool, RiskLevel, ToolCategory, ToolResult

logger = get_logger(__name__)


@dataclass
class ScheduledJob:
    job_id: str
    name: str
    workflow_id: str
    risk: str
    interval_s: float
    next_run_ts: float
    last_run_ts: float = 0.0
    enabled: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


class WorkflowScheduler:
    """Persistent scheduler for automated workflows."""

    def __init__(self, storage_path: Path | None = None) -> None:
        if storage_path is None:
            repo_root = Path(__file__).resolve().parent.parent.parent
            self.storage_path = repo_root / "data" / "schedules.json"
        else:
            self.storage_path = storage_path

        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self.jobs: dict[str, ScheduledJob] = {}
        self._load_jobs()

    def _load_jobs(self) -> None:
        """Loads persistent schedules from disk."""
        if not self.storage_path.exists():
            return
        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for item in data:
                job = ScheduledJob(**item)
                self.jobs[job.job_id] = job
            logger.info("scheduler_jobs_loaded", count=len(self.jobs))
        except Exception as e:
            logger.error("scheduler_load_error", error=str(e))

    def _save_jobs(self) -> None:
        """Persists schedules to disk so they survive restarts."""
        try:
            items = [asdict(j) for j in self.jobs.values()]
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump(items, f, indent=2)
        except Exception as e:
            logger.error("scheduler_save_error", error=str(e))

    def schedule(
        self,
        job_id: str,
        name: str,
        workflow_id: str,
        risk: RiskLevel | str,
        interval_s: float,
    ) -> dict[str, Any]:
        """Schedules a workflow.

        SAFETY INVARIANT: HIGH-risk workflows are strictly refused.
        """
        risk_str = risk.value if isinstance(risk, RiskLevel) else str(risk).lower()

        if risk_str == "high":
            logger.warning("scheduler_high_risk_refused", workflow_id=workflow_id)
            return {
                "success": False,
                "error": "HIGH-risk schedule refused: Unattended automated execution of HIGH-risk workflows is prohibited.",
            }

        next_run = time.time() + interval_s
        job = ScheduledJob(
            job_id=job_id,
            name=name,
            workflow_id=workflow_id,
            risk=risk_str,
            interval_s=interval_s,
            next_run_ts=next_run,
        )
        self.jobs[job_id] = job
        self._save_jobs()
        logger.info("workflow_scheduled", job_id=job_id, next_run=next_run)

        return {
            "success": True,
            "job_id": job_id,
            "name": name,
            "next_run_ts": next_run,
            "message": f"Successfully scheduled workflow '{name}' (survives restart).",
        }

    def cancel(self, job_id: str) -> bool:
        """Cancels and removes a scheduled job."""
        if job_id in self.jobs:
            del self.jobs[job_id]
            self._save_jobs()
            return True
        return False

    def list_jobs(self) -> list[dict[str, Any]]:
        """Returns list of all active scheduled jobs."""
        return [asdict(j) for j in self.jobs.values()]


class SchedulerTool(BaseTool):
    """Tool to manage persistent workflow schedules."""

    name = "workflow.schedule"
    description = (
        "Schedule workflows for recurring background execution. "
        "Schedules survive restart. HIGH-risk schedules are strictly refused."
    )
    category = ToolCategory.SYSTEM
    risk = RiskLevel.MEDIUM
    timeout_s = 15
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["schedule", "list", "cancel"],
                "description": "Scheduler action.",
            },
            "job_id": {"type": "string", "description": "Unique identifier for the scheduled job."},
            "name": {"type": "string", "description": "Descriptive name for the job."},
            "workflow_id": {"type": "string", "description": "ID of workflow to execute."},
            "risk": {"type": "string", "enum": ["low", "medium", "high"], "description": "Risk level of workflow."},
            "interval_s": {"type": "number", "description": "Recurring interval in seconds."},
        },
        "required": ["action"],
    }

    def __init__(self, scheduler: WorkflowScheduler | None = None) -> None:
        super().__init__()
        self.scheduler = scheduler or WorkflowScheduler()

    async def run(self, args: dict[str, Any]) -> ToolResult:
        return await self.execute(**args)

    async def execute(self, **kwargs: Any) -> ToolResult:
        action = kwargs.get("action", "list")

        if action == "list":
            jobs = self.scheduler.list_jobs()
            if not jobs:
                return ToolResult.ok("No active scheduled workflows.")
            lines = [f"Found {len(jobs)} scheduled workflow(s):"]
            for j in jobs:
                lines.append(f"- ID: {j['job_id']}, Name: '{j['name']}', Risk: {j['risk']}, Interval: {j['interval_s']}s")
            return ToolResult.ok("\n".join(lines), data=jobs)

        elif action == "schedule":
            job_id = kwargs.get("job_id", f"job_{int(time.time())}")
            name = kwargs.get("name", "Unnamed Job")
            workflow_id = kwargs.get("workflow_id", "")
            risk = kwargs.get("risk", "low")
            interval_s = float(kwargs.get("interval_s", 3600.0))

            res = self.scheduler.schedule(job_id, name, workflow_id, risk, interval_s)
            if not res["success"]:
                return ToolResult.error_result(res["error"])
            return ToolResult.ok(res["message"], data=res)

        elif action == "cancel":
            job_id = kwargs.get("job_id", "")
            if not job_id:
                return ToolResult.error_result("Argument 'job_id' is required for cancellation.")
            canceled = self.scheduler.cancel(job_id)
            if canceled:
                return ToolResult.ok(f"Cancelled schedule '{job_id}'.")
            return ToolResult.error_result(f"Schedule '{job_id}' not found.")

        return ToolResult.error_result(f"Unknown scheduler action: '{action}'")
