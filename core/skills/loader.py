"""T.A.R.O. - Skill loader (TASK-070).

ARCHITECTURE reference: section 13 (Skills).
RULES reference: section 3, 10.
TASKS: TASK-070.

Loads skills from folders under `skills/`:
  skills/<name>/
    SKILL.md
    skill.json
    execution.py

Acceptance (TASK-070):
- Skill with bad skill.json skipped and logged.
- Supports discovery, enable, and disable.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any, Callable

from core.log.setup import get_logger
from core.skills.validator import validate_skill_metadata
from core.tools.base import BaseTool, RiskLevel, ToolCategory, ToolResult

logger = get_logger(__name__)


class SkillToolAdapter(BaseTool):
    """Adapts a skill folder execution.py into a BaseTool for the orchestrator."""

    def __init__(
        self,
        name: str,
        description: str,
        category: ToolCategory,
        risk: RiskLevel,
        parameters: dict[str, Any],
        run_func: Callable[[dict[str, Any]], Any],
        skill_dir: Path,
        version: str = "1.0.0",
        timeout_s: int = 30,
    ) -> None:
        self.name = f"skill.{name}"
        self.description = description
        self.category = category
        self.risk = risk
        self.parameters = parameters
        self.run_func = run_func
        self.skill_dir = skill_dir
        self.version = version
        self.timeout_s = timeout_s

    async def run(self, args: dict[str, Any]) -> ToolResult:
        return await self.execute(**args)

    async def execute(self, **kwargs: Any) -> ToolResult:
        try:
            import inspect

            if inspect.iscoroutinefunction(self.run_func):
                res = await self.run_func(kwargs)
            else:
                res = self.run_func(kwargs)

            if isinstance(res, ToolResult):
                return res
            if isinstance(res, dict):
                status = res.get("status", "ok")
                output = res.get("output", str(res))
                error = res.get("error", "")
                if status == "ok":
                    return ToolResult.ok(output)
                elif status == "denied":
                    return ToolResult.denied(error or output)
                else:
                    return ToolResult.error_result(error or output)
            return ToolResult.ok(str(res))
        except Exception as e:
            logger.error("skill_execution_error", skill=self.name, error=str(e))
            return ToolResult.error_result(f"Skill '{self.name}' execution failed: {e}")


class SkillLoader:
    """Discovers, validates, and loads skill packages."""

    def __init__(self, skills_dir: Path | str | None = None) -> None:
        if skills_dir is None:
            self.skills_dir = Path("skills")
        else:
            self.skills_dir = Path(skills_dir)
        self.loaded_skills: dict[str, SkillToolAdapter] = {}
        self.disabled_skills: set[str] = set()
        self.failed_skills: dict[str, str] = {}  # folder_name -> reason

    def discover_and_load_all(self) -> list[SkillToolAdapter]:
        """Scans skills directory, loads valid skills, skips bad ones."""
        self.loaded_skills.clear()
        self.failed_skills.clear()

        if not self.skills_dir.exists():
            logger.info("skills_directory_not_found", path=str(self.skills_dir))
            return []

        for folder in self.skills_dir.iterdir():
            if not folder.is_dir() or folder.name.startswith(("_", ".")):
                continue

            skill = self.load_skill(folder)
            if skill is not None:
                if folder.name in self.disabled_skills:
                    logger.info("skill_disabled_by_config", skill=folder.name)
                else:
                    self.loaded_skills[folder.name] = skill

        logger.info(
            "skills_loaded_summary",
            loaded=len(self.loaded_skills),
            failed=len(self.failed_skills),
            disabled=len(self.disabled_skills),
        )
        return list(self.loaded_skills.values())

    def load_skill(self, folder: Path) -> SkillToolAdapter | None:
        """Loads a single skill folder. Returns None if invalid or failed."""
        folder_name = folder.name
        skill_json_path = folder / "skill.json"
        execution_py_path = folder / "execution.py"

        if not skill_json_path.exists():
            reason = f"Missing skill.json in {folder.name}"
            logger.warning("skill_missing_metadata", folder=folder.name)
            self.failed_skills[folder_name] = reason
            return None

        # 1. Parse skill.json
        try:
            with open(skill_json_path, "r", encoding="utf-8") as f:
                metadata = json.load(f)
        except Exception as e:
            reason = f"Corrupted or invalid JSON in skill.json: {e}"
            logger.warning("skill_bad_json", folder=folder.name, error=str(e))
            self.failed_skills[folder_name] = reason
            return None

        # 2. Validate metadata
        valid, reason = validate_skill_metadata(metadata, folder_name=folder_name)
        if not valid:
            logger.warning("skill_validation_failed", folder=folder.name, reason=reason)
            self.failed_skills[folder_name] = reason
            return None

        # 3. Check execution.py
        if not execution_py_path.exists():
            reason = f"Missing execution.py in {folder.name}"
            logger.warning("skill_missing_execution", folder=folder.name)
            self.failed_skills[folder_name] = reason
            return None

        # 4. Import execution.py
        try:
            spec = importlib.util.spec_from_file_location(
                f"taro_skill_{folder_name}", execution_py_path
            )
            if spec is None or spec.loader is None:
                raise ImportError(f"Cannot load module spec for {execution_py_path}")
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)

            run_func = getattr(mod, "run", None)
            if not callable(run_func):
                reason = f"execution.py in {folder.name} missing callable 'run(args)'"
                logger.warning("skill_missing_run_callable", folder=folder.name)
                self.failed_skills[folder_name] = reason
                return None

            adapter = SkillToolAdapter(
                name=metadata["name"],
                description=metadata["description"],
                category=ToolCategory(metadata["category"].lower()),
                risk=RiskLevel(metadata["risk"].upper()),
                parameters=metadata.get("inputs", {"type": "object"}),
                run_func=run_func,
                skill_dir=folder,
                version=metadata.get("version", "1.0.0"),
            )
            logger.info("skill_successfully_loaded", skill=metadata["name"])
            return adapter

        except Exception as e:
            reason = f"Failed to import execution.py: {e}"
            logger.error("skill_import_error", folder=folder.name, error=str(e))
            self.failed_skills[folder_name] = reason
            return None

    def enable_skill(self, name: str) -> bool:
        """Enable a skill."""
        if name in self.disabled_skills:
            self.disabled_skills.remove(name)
        folder = self.skills_dir / name
        if folder.exists():
            skill = self.load_skill(folder)
            if skill:
                self.loaded_skills[name] = skill
                return True
        return False

    def disable_skill(self, name: str) -> None:
        """Disable a skill."""
        self.disabled_skills.add(name)
        if name in self.loaded_skills:
            del self.loaded_skills[name]
        logger.info("skill_disabled", skill=name)
