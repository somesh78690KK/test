"""T.A.R.O. - Skill health monitor (TASK-119).

ARCHITECTURE reference: section 18.
TASKS: TASK-119.

Tracks skill execution success/failure rates and offers repair when
a skill fails 3 times in a row.

Acceptance (TASK-119): 3 failures in a row trigger a repair offer.
"""

from __future__ import annotations

import json
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

from core.log.setup import get_logger

logger = get_logger(__name__)

HEALTH_FILE = Path("data/skill_health.json")
CONSECUTIVE_FAILURE_THRESHOLD = 3


class SkillHealthMonitor:
    """Monitors skill execution health and triggers repair offers."""

    def __init__(self, health_path: Path | str | None = None) -> None:
        self._path = Path(health_path) if health_path else HEALTH_FILE
        self._records: dict[str, dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        if self._path.exists():
            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    self._records = json.load(f)
            except (json.JSONDecodeError, OSError):
                self._records = {}

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(self._records, f, indent=2)

    def record_success(self, skill_name: str) -> None:
        """Record a successful skill execution."""
        rec = self._records.setdefault(skill_name, {
            "total_runs": 0, "successes": 0, "failures": 0,
            "consecutive_failures": 0, "last_error": None,
        })
        rec["total_runs"] += 1
        rec["successes"] += 1
        rec["consecutive_failures"] = 0
        rec["last_success"] = time.time()
        self._save()

    def record_failure(self, skill_name: str, error: str = "") -> dict[str, Any] | None:
        """Record a skill failure. Returns a repair offer if threshold met."""
        rec = self._records.setdefault(skill_name, {
            "total_runs": 0, "successes": 0, "failures": 0,
            "consecutive_failures": 0, "last_error": None,
        })
        rec["total_runs"] += 1
        rec["failures"] += 1
        rec["consecutive_failures"] = rec.get("consecutive_failures", 0) + 1
        rec["last_error"] = error
        rec["last_failure"] = time.time()
        self._save()

        if rec["consecutive_failures"] >= CONSECUTIVE_FAILURE_THRESHOLD:
            logger.warning(
                "skill_repair_triggered",
                name=skill_name,
                consecutive_failures=rec["consecutive_failures"],
            )
            return {
                "type": "repair_offer",
                "skill_name": skill_name,
                "consecutive_failures": rec["consecutive_failures"],
                "last_error": error,
                "success_rate": (
                    f"{rec['successes']}/{rec['total_runs']}"
                    if rec["total_runs"] > 0 else "0/0"
                ),
            }
        return None

    def get_health(self, skill_name: str) -> dict[str, Any]:
        """Get health stats for a specific skill."""
        return self._records.get(skill_name, {
            "total_runs": 0, "successes": 0, "failures": 0,
            "consecutive_failures": 0, "last_error": None,
        })

    def get_all_health(self) -> dict[str, dict[str, Any]]:
        """Get health for all tracked skills."""
        return dict(self._records)

    def reset_health(self, skill_name: str) -> None:
        """Reset health stats for a skill (e.g. after repair)."""
        if skill_name in self._records:
            self._records[skill_name] = {
                "total_runs": 0, "successes": 0, "failures": 0,
                "consecutive_failures": 0, "last_error": None,
            }
            self._save()
            logger.info("skill_health_reset", name=skill_name)

    def needs_repair(self, skill_name: str) -> bool:
        """Check if a skill needs repair."""
        rec = self._records.get(skill_name, {})
        return rec.get("consecutive_failures", 0) >= CONSECUTIVE_FAILURE_THRESHOLD
