"""T.A.R.O. - Workflow manager & stats tracker (TASK-076).

ARCHITECTURE reference: section 11.
RULES reference: section 3, 10.
TASKS: TASK-076.

Manages saved workflows:
- List, save, rename, and delete workflows.
- Tracks execution metrics (total runs, successful runs, and success rate).
- Updates success rate after each replay.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.log.setup import get_logger

logger = get_logger(__name__)


class WorkflowManager:
    """Manages workflow persistence and performance metrics."""

    def __init__(self, storage_dir: Path | str | None = None) -> None:
        self.storage_dir = Path(storage_dir) if storage_dir else Path("data/workflows")
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.stats_file = self.storage_dir / "workflow_stats.json"
        self._stats: dict[str, dict[str, Any]] = self._load_stats()

    def _load_stats(self) -> dict[str, dict[str, Any]]:
        if self.stats_file.exists():
            try:
                with open(self.stats_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def _save_stats(self) -> None:
        try:
            with open(self.stats_file, "w", encoding="utf-8") as f:
                json.dump(self._stats, f, indent=2)
        except Exception as e:
            logger.error("failed_to_save_workflow_stats", error=str(e))

    def save_workflow(self, workflow: dict[str, Any]) -> Path:
        """Save or update a compiled workflow."""
        name = workflow.get("name", "unnamed")
        target = self.storage_dir / f"{name}.json"
        with open(target, "w", encoding="utf-8") as f:
            json.dump(workflow, f, indent=2)

        if name not in self._stats:
            self._stats[name] = {"total_runs": 0, "successful_runs": 0, "success_rate": 0.0}
            self._save_stats()

        logger.info("workflow_saved", name=name, path=str(target))
        return target

    def list_workflows(self) -> list[dict[str, Any]]:
        """List all available workflows with their current success rates."""
        results = []
        for p in self.storage_dir.glob("*.json"):
            if p.name == "workflow_stats.json":
                continue
            try:
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                name = data.get("name", p.stem)
                stats = self._stats.get(name, {"total_runs": 0, "successful_runs": 0, "success_rate": 0.0})
                results.append({
                    "name": name,
                    "description": data.get("description", ""),
                    "step_count": len(data.get("steps", [])),
                    "total_runs": stats.get("total_runs", 0),
                    "success_rate": stats.get("success_rate", 0.0),
                    "path": str(p),
                })
            except Exception:
                continue
        return results

    def get_workflow(self, name: str) -> dict[str, Any] | None:
        """Retrieve a workflow by name."""
        p = self.storage_dir / f"{name}.json"
        if not p.exists():
            return None
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)

    def rename_workflow(self, old_name: str, new_name: str) -> bool:
        """Rename an existing workflow."""
        old_path = self.storage_dir / f"{old_name}.json"
        new_path = self.storage_dir / f"{new_name}.json"
        if not old_path.exists() or new_path.exists():
            return False

        with open(old_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        data["name"] = new_name

        with open(new_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        old_path.unlink()

        if old_name in self._stats:
            self._stats[new_name] = self._stats.pop(old_name)
            self._save_stats()

        logger.info("workflow_renamed", old=old_name, new=new_name)
        return True

    def delete_workflow(self, name: str) -> bool:
        """Delete a workflow."""
        p = self.storage_dir / f"{name}.json"
        if not p.exists():
            return False
        p.unlink()
        self._stats.pop(name, None)
        self._save_stats()
        logger.info("workflow_deleted", name=name)
        return True

    def record_replay_result(self, name: str, success: bool) -> float:
        """Record execution outcome and return updated success rate (TASK-076)."""
        if name not in self._stats:
            self._stats[name] = {"total_runs": 0, "successful_runs": 0, "success_rate": 0.0}

        st = self._stats[name]
        st["total_runs"] += 1
        if success:
            st["successful_runs"] += 1

        new_rate = round((st["successful_runs"] / st["total_runs"]) * 100.0, 1)
        st["success_rate"] = new_rate
        self._save_stats()
        logger.info("workflow_stats_updated", name=name, total=st["total_runs"], rate=new_rate)
        return new_rate

    def export_as_skill(self, name: str, target_skills_dir: Path | str | None = None) -> Path:
        """Export a workflow as a callable skill package (TASK-120)."""
        wf = self.get_workflow(name)
        if not wf:
            raise FileNotFoundError(f"Workflow '{name}' does not exist.")

        skills_dir = Path(target_skills_dir) if target_skills_dir else Path("skills")
        skill_dir = skills_dir / name
        skill_dir.mkdir(parents=True, exist_ok=True)

        # 1. skill.json
        skill_json = {
            "name": name,
            "version": "1.0.0",
            "description": f"Automated workflow skill for {name}",
            "category": "training",
            "risk": "LOW",
            "required_permissions": ["system"],
            "inputs": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        }
        with open(skill_dir / "skill.json", "w", encoding="utf-8") as f:
            json.dump(skill_json, f, indent=2)

        # 2. SKILL.md
        skill_md = (
            f"# Skill: {name}\n\n"
            f"No-code workflow skill automatically generated from recorded workflow `{name}`.\n\n"
            f"- Steps count: {len(wf.get('steps', []))}\n"
            f"- Category: training\n"
            f"- Risk: LOW\n"
        )
        with open(skill_dir / "SKILL.md", "w", encoding="utf-8") as f:
            f.write(skill_md)

        # 3. execution.py
        wf_escaped = json.dumps(wf)
        execution_py = (
            f'"""Automated execution wrapper for workflow {name}."""\n\n'
            f'import asyncio\n'
            f'import json\n'
            f'from typing import Any\n'
            f'from capabilities.training.replayer import WorkflowReplayer\n\n'
            f'WORKFLOW_DATA = json.loads({json.dumps(wf_escaped)})\n\n'
            f'def run(args: dict[str, Any]) -> dict[str, Any]:\n'
            f'    """Execute the workflow replay."""\n'
            f'    replayer = WorkflowReplayer()\n'
            f'    try:\n'
            f'        loop = asyncio.get_event_loop()\n'
            f'        if loop.is_running():\n'
            f'            # Running within active loop\n'
            f'            import concurrent.futures\n'
            f'            with concurrent.futures.ThreadPoolExecutor() as pool:\n'
            f'                return pool.submit(asyncio.run, replayer.replay(WORKFLOW_DATA)).result()\n'
            f'        else:\n'
            f'            return loop.run_until_complete(replayer.replay(WORKFLOW_DATA))\n'
            f'    except RuntimeError:\n'
            f'        return asyncio.run(replayer.replay(WORKFLOW_DATA))\n'
        )
        with open(skill_dir / "execution.py", "w", encoding="utf-8") as f:
            f.write(execution_py)

        logger.info("workflow_exported_as_skill", name=name, path=str(skill_dir))
        return skill_dir

