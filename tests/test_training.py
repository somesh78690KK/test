"""Tests for T.A.R.O. Training & Workflow automation (TASK-073, TASK-074, TASK-075, TASK-076)."""

import json
from pathlib import Path

import pytest

from capabilities.training.compiler import compile_workflow
from capabilities.training.manager import WorkflowManager
from capabilities.training.recorder import TrainingRecorder
from capabilities.training.replayer import WorkflowReplayer


# --- TASK-073: Training Recorder ---

def test_task_073_recorder_privacy_and_jsonl(tmp_path: Path):
    """TASK-073: Recording 50 events saved as JSON lines; password fields not stored."""
    rec = TrainingRecorder(output_dir=tmp_path)
    rec.start_recording()
    assert rec.is_recording is True

    # Record 40 normal events
    for i in range(40):
        rec.record_event(
            event_type="key_press",
            data={"key": "a"},
            active_window_title="Notepad - document.txt",
        )

    # Record 10 events in a password field / sensitive window
    for i in range(10):
        rec.record_event(
            event_type="key_press",
            data={"key": "secret_password_character"},
            active_window_title="Login - Enter Master Password",
            is_password_field=True,
        )

    out_file = rec.stop_recording(filename="test_session.jsonl")
    assert rec.is_recording is False
    assert out_file.exists()

    # Verify JSONL lines and privacy masking
    lines = out_file.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 50

    # Ensure secret_password_character is never stored
    raw_content = out_file.read_text(encoding="utf-8")
    assert "secret_password_character" not in raw_content
    assert "[MASKED_PASSWORD_FIELD]" in raw_content


# --- TASK-074: Workflow Compiler ---

def test_task_074_workflow_compiler_groups_and_attaches_window():
    """TASK-074: Workflow compiler groups keys into type_text and attaches window context."""
    raw_events = [
        {"type": "click", "x": 100, "y": 200, "button": "left", "window": "Notepad"},
        {"type": "key_press", "key": "h", "window": "Notepad"},
        {"type": "key_press", "key": "e", "window": "Notepad"},
        {"type": "key_press", "key": "l", "window": "Notepad"},
        {"type": "key_press", "key": "l", "window": "Notepad"},
        {"type": "key_press", "key": "o", "window": "Notepad"},
        {"type": "key_press", "key": "space", "window": "Notepad"},
        {"type": "key_press", "key": "w", "window": "Notepad"},
        {"type": "key_press", "key": "o", "window": "Notepad"},
        {"type": "key_press", "key": "r", "window": "Notepad"},
        {"type": "key_press", "key": "l", "window": "Notepad"},
        {"type": "key_press", "key": "d", "window": "Notepad"},
    ]

    workflow = compile_workflow(raw_events, workflow_name="type_hello")
    assert workflow["name"] == "type_hello"
    steps = workflow["steps"]

    # Click + grouped text
    assert len(steps) == 2
    assert steps[0]["action"] == "click"
    assert steps[0]["x"] == 100
    assert steps[0]["target_window"] == "Notepad"

    assert steps[1]["action"] == "type_text"
    assert steps[1]["text"] == "hello world"
    assert steps[1]["target_window"] == "Notepad"


# --- TASK-075: Workflow Replayer ---

@pytest.mark.asyncio
async def test_task_075_replay_stops_on_window_mismatch():
    """TASK-075: Replay stops immediately on window mismatch."""
    workflow = {
        "name": "critical_task",
        "steps": [
            {"action": "click", "x": 50, "y": 50, "target_window": "Calculated App"},
            {"action": "type_text", "text": "123", "target_window": "Calculated App"},
        ],
    }

    # Simulate foreground window being 'Browser - Web' instead of 'Calculated App'
    replayer = WorkflowReplayer(get_active_window_func=lambda: "Browser - Web")
    res = await replayer.replay(workflow)

    assert res["status"] == "failed"
    assert res["completed_steps"] == 0
    assert "Window mismatch" in res["error"]
    assert "Expected 'Calculated App'" in res["error"]


@pytest.mark.asyncio
async def test_task_075_replay_succeeds_when_window_matches():
    """TASK-075: Replay succeeds when active window matches."""
    executed = []
    workflow = {
        "name": "safe_task",
        "steps": [
            {"action": "click", "x": 10, "y": 20, "target_window": "Notepad"},
            {"action": "type_text", "text": "hi", "target_window": "Notepad"},
        ],
    }

    replayer = WorkflowReplayer(
        get_active_window_func=lambda: "Untitled - Notepad",
        step_executor=lambda step: executed.append(step["action"]),
    )
    res = await replayer.replay(workflow)

    assert res["status"] == "ok"
    assert res["completed_steps"] == 2
    assert executed == ["click", "type_text"]


# --- TASK-076: Workflow Manager & Success Rate ---

def test_task_076_workflow_management_and_success_rate(tmp_path: Path):
    """TASK-076: Workflow manager CRUD and success rate updates after each replay."""
    mgr = WorkflowManager(storage_dir=tmp_path)

    # 1. Save workflow
    wf_data = {"name": "auto_backup", "steps": [{"action": "click"}]}
    mgr.save_workflow(wf_data)

    listed = mgr.list_workflows()
    assert len(listed) == 1
    assert listed[0]["name"] == "auto_backup"
    assert listed[0]["success_rate"] == 0.0

    # 2. Record successful replay -> 100%
    rate1 = mgr.record_replay_result("auto_backup", success=True)
    assert rate1 == 100.0

    # 3. Record failed replay -> 50%
    rate2 = mgr.record_replay_result("auto_backup", success=False)
    assert rate2 == 50.0

    # 4. Record another successful replay -> 66.7%
    rate3 = mgr.record_replay_result("auto_backup", success=True)
    assert rate3 == 66.7

    # 5. Rename workflow
    renamed = mgr.rename_workflow("auto_backup", "auto_backup_v2")
    assert renamed is True
    assert mgr.get_workflow("auto_backup") is None
    assert mgr.get_workflow("auto_backup_v2") is not None
    assert mgr._stats["auto_backup_v2"]["success_rate"] == 66.7

    # 6. Delete workflow
    deleted = mgr.delete_workflow("auto_backup_v2")
    assert deleted is True
    assert len(mgr.list_workflows()) == 0


# --- TASK-120: Workflow saved as a callable skill ---

def test_task_120_workflow_saved_as_callable_skill(tmp_path: Path):
    """TASK-120 acceptance: Workflow saved as a callable skill package that passes validator."""
    from core.skills.loader import SkillLoader

    mgr = WorkflowManager(storage_dir=tmp_path / "workflows")
    wf_data = {
        "name": "daily_cleaner",
        "steps": [
            {"action": "click", "x": 100, "y": 200, "target_window": "Explorer"},
            {"action": "type_text", "text": "clean", "target_window": "Explorer"},
        ],
    }
    mgr.save_workflow(wf_data)

    skills_dir = tmp_path / "skills"
    skill_path = mgr.export_as_skill("daily_cleaner", target_skills_dir=skills_dir)
    assert skill_path.exists()
    assert (skill_path / "skill.json").exists()
    assert (skill_path / "SKILL.md").exists()
    assert (skill_path / "execution.py").exists()

    # Verify with validate_skill_metadata
    from core.skills.validator import validate_skill_metadata
    with open(skill_path / "skill.json", "r", encoding="utf-8") as f:
        meta = json.load(f)
    valid, err = validate_skill_metadata(meta, folder_name="daily_cleaner")
    assert valid is True
    assert err == ""

    # Verify with SkillLoader
    loader = SkillLoader(skills_dir=skills_dir)
    loaded = loader.discover_and_load_all()
    assert len(loaded) == 1
    assert "daily_cleaner" in loader.loaded_skills
    tool = loader.loaded_skills["daily_cleaner"]
    assert tool.name == "skill.daily_cleaner"

