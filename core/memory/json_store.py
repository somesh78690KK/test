"""T.A.R.O. - Tier 3 Procedural Memory (JSON).

ARCHITECTURE reference: section 12.
MEMORY reference: section 3 (Tier 3).
TASKS: TASK-060.

Manages procedural records in data/procedural/:
- workflows/<name>.json
- trusted_actions.json
- permission_log.json
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.log.setup import get_logger

logger = get_logger(__name__)


class JSONProceduralStore:
    """Tier 3 JSON storage for workflows, trusted actions, and procedural state."""

    def __init__(self, base_dir: Path | str = "data/procedural") -> None:
        self.base_dir = Path(base_dir)
        self.workflows_dir = self.base_dir / "workflows"
        self.workflows_dir.mkdir(parents=True, exist_ok=True)
        self.trusted_actions_file = self.base_dir / "trusted_actions.json"
        self.permission_log_file = self.base_dir / "permission_log.json"

    def save_workflow(self, name: str, data: dict[str, Any]) -> Path:
        """Save a recorded and compiled workflow definition."""
        safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)
        file_path = self.workflows_dir / f"{safe_name}.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        logger.info("workflow_saved", name=name, path=str(file_path))
        return file_path

    def load_workflow(self, name: str) -> dict[str, Any] | None:
        """Load a workflow by name."""
        safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)
        file_path = self.workflows_dir / f"{safe_name}.json"
        if not file_path.exists():
            return None
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def list_workflows(self) -> list[str]:
        """List all available workflow names."""
        return [f.stem for f in self.workflows_dir.glob("*.json")]

    def log_permission_decision(
        self,
        action: str,
        decision: str,
        risk: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Append a permission decision to the JSON log."""
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": action,
            "decision": decision,
            "risk": risk,
            "details": details or {},
        }
        records: list[dict[str, Any]] = []
        if self.permission_log_file.exists():
            try:
                with open(self.permission_log_file, "r", encoding="utf-8") as f:
                    records = json.load(f)
            except Exception:
                records = []

        records.append(record)
        with open(self.permission_log_file, "w", encoding="utf-8") as f:
            json.dump(records, f, indent=2)


# Singleton
_json_store: JSONProceduralStore | None = None


def get_json_store(base_dir: Path | str | None = None) -> JSONProceduralStore:
    """Return singleton JSON store."""
    global _json_store
    if _json_store is None or base_dir is not None:
        _json_store = JSONProceduralStore(base_dir or "data/procedural")
    return _json_store
