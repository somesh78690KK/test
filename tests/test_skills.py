"""Tests for T.A.R.O. Skills subsystem (TASK-070, TASK-071, TASK-072)."""

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from core.safety.permissions import PermissionAction, PermissionDenied, PermissionManager
from core.skills.loader import SkillLoader
from core.skills.validator import validate_skill_metadata
from core.tools.base import RiskLevel, ToolCategory


# --- TASK-070: Skill Loader & Error Handling ---

def test_task_070_skill_loader_skips_bad_skill_json(tmp_path: Path):
    """TASK-070: Skill with bad skill.json is skipped and logged."""
    skills_root = tmp_path / "skills"
    skills_root.mkdir()

    # 1. Create a corrupted skill folder (invalid JSON)
    bad_json_dir = skills_root / "bad_json_skill"
    bad_json_dir.mkdir()
    (bad_json_dir / "skill.json").write_text("{ this is not valid json }", encoding="utf-8")
    (bad_json_dir / "execution.py").write_text("def run(args): pass", encoding="utf-8")

    # 2. Create a skill missing required fields
    missing_fields_dir = skills_root / "missing_fields_skill"
    missing_fields_dir.mkdir()
    (missing_fields_dir / "skill.json").write_text(
        json.dumps({"name": "missing_fields_skill"}), encoding="utf-8"
    )
    (missing_fields_dir / "execution.py").write_text("def run(args): pass", encoding="utf-8")

    # 3. Create a valid skill
    good_dir = skills_root / "good_skill"
    good_dir.mkdir()
    (good_dir / "skill.json").write_text(
        json.dumps({
            "name": "good_skill",
            "version": "1.0.0",
            "description": "A valid test skill",
            "category": "files",
            "risk": "LOW",
            "inputs": {"type": "object", "properties": {}},
        }),
        encoding="utf-8",
    )
    (good_dir / "execution.py").write_text(
        "def run(args):\n    return {'status': 'ok', 'output': 'good'}", encoding="utf-8"
    )

    loader = SkillLoader(skills_dir=skills_root)
    loaded = loader.discover_and_load_all()

    # Verify: bad skills skipped, good skill loaded
    assert len(loaded) == 1
    assert "good_skill" in loader.loaded_skills
    assert "bad_json_skill" in loader.failed_skills
    assert "missing_fields_skill" in loader.failed_skills


def test_task_070_skill_enable_disable(tmp_path: Path):
    """TASK-070: Skill loader supports enabling and disabling skills."""
    skills_root = tmp_path / "skills"
    skills_root.mkdir()

    good_dir = skills_root / "test_toggle"
    good_dir.mkdir()
    (good_dir / "skill.json").write_text(
        json.dumps({
            "name": "test_toggle",
            "version": "1.0.0",
            "description": "Toggle skill",
            "category": "system",
            "risk": "SAFE",
            "inputs": {"type": "object"},
        }),
        encoding="utf-8",
    )
    (good_dir / "execution.py").write_text(
        "def run(args):\n    return {'status': 'ok'}", encoding="utf-8"
    )

    loader = SkillLoader(skills_dir=skills_root)
    loader.discover_and_load_all()
    assert "test_toggle" in loader.loaded_skills

    # Disable skill
    loader.disable_skill("test_toggle")
    assert "test_toggle" not in loader.loaded_skills
    assert "test_toggle" in loader.disabled_skills

    # Re-enable skill
    success = loader.enable_skill("test_toggle")
    assert success is True
    assert "test_toggle" in loader.loaded_skills
    assert "test_toggle" not in loader.disabled_skills


# --- TASK-071: Skill Validator & Permission Enforcement ---

def test_task_071_validator_schema_checks():
    """TASK-071: Skill validator rejects bad names, invalid categories, or bad risks."""
    base_valid = {
        "name": "my_skill",
        "version": "1.0.0",
        "description": "Valid description",
        "category": "files",
        "risk": "LOW",
        "inputs": {"type": "object"},
    }

    # Invalid name (camelCase instead of snake_case)
    bad_name = dict(base_valid, name="mySkill")
    valid, reason = validate_skill_metadata(bad_name)
    assert not valid
    assert "snake_case" in reason

    # Mismatched folder name
    valid, reason = validate_skill_metadata(base_valid, folder_name="different_name")
    assert not valid
    assert "does not match folder name" in reason

    # Invalid category
    bad_cat = dict(base_valid, category="nonexistent_category")
    valid, reason = validate_skill_metadata(bad_cat)
    assert not valid
    assert "Invalid category" in reason

    # Invalid risk
    bad_risk = dict(base_valid, risk="EXTREME_DANGER")
    valid, reason = validate_skill_metadata(bad_risk)
    assert not valid
    assert "Invalid risk level" in reason


def test_task_071_skill_needing_ungranted_permission_rejected():
    """TASK-071: Skill needing an ungranted/denied permission is not loaded."""
    mock_pm = MagicMock(spec=PermissionManager)
    mock_pm.categories = {"cloud": PermissionAction.DENY}
    mock_pm.evaluate.side_effect = PermissionDenied(category="cloud", reason="Blocked by policy")

    skill_meta = {
        "name": "cloud_sync",
        "version": "1.0.0",
        "description": "Upload to external cloud",
        "category": "cloud",
        "risk": "HIGH",
        "permissions": ["cloud.upload"],
        "inputs": {"type": "object"},
    }

    valid, reason = validate_skill_metadata(skill_meta, permission_manager=mock_pm)
    assert not valid
    assert "Permission denied" in reason or "denied" in reason


# --- TASK-072: Built-in Skills Verification ---

def test_task_072_builtin_skills_load_and_pass_validation():
    """TASK-072: Built-in skills have SKILL.md, skill.json, pass validation, and load cleanly."""
    loader = SkillLoader(skills_dir="skills")
    skills = loader.discover_and_load_all()

    # At least excel_automation, file_organizer, system_info must be loaded
    loaded_names = {s.name for s in skills}
    assert "skill.excel_automation" in loaded_names
    assert "skill.file_organizer" in loaded_names
    assert "skill.system_info" in loaded_names
    assert len(loader.failed_skills) == 0


@pytest.mark.asyncio
async def test_task_072_builtin_skill_execution(tmp_path: Path):
    """TASK-072: Built-in skills execute correctly."""
    loader = SkillLoader(skills_dir="skills")
    loader.discover_and_load_all()

    # 1. Test system_info
    sys_tool = loader.loaded_skills["system_info"]
    res = await sys_tool.execute()
    assert res.status == "ok"
    assert "OS:" in res.output

    # 2. Test excel_automation
    excel_tool = loader.loaded_skills["excel_automation"]
    test_xlsx = tmp_path / "test.xlsx"
    res_create = await excel_tool.execute(
        action="create",
        filepath=str(test_xlsx),
        data=[["Header1", "Header2"], ["Val1", "Val2"]],
    )
    assert res_create.status == "ok"
    assert test_xlsx.exists()

    res_read = await excel_tool.execute(
        action="read",
        filepath=str(test_xlsx),
    )
    assert res_read.status == "ok"
    assert "Read 2 rows" in res_read.output
