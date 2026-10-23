"""T.A.R.O. - Phase 6c Capabilities Acceptance Tests.

Tests for:
- TASK-130: InputControlTool
- TASK-131: ExplorerAutomationTool
- TASK-132: AppIntel & discovery
- TASK-133: UIFindTool
- TASK-134: UIActTool
- TASK-135: ScreenWatchTool
- TASK-136: ShellTemplateTool
- TASK-137: SecurityGuardian
- TASK-138: NotificationGuardian
- TASK-139: WorkflowScheduler
- TASK-142: ModelRouter
- TASK-144: UsageAnalytics
- TASK-145: DocumentQATool
"""

from __future__ import annotations

import asyncio
import os
import tempfile
from pathlib import Path

import pytest
from capabilities.coding.shell_templates import ShellTemplateTool
from capabilities.notes.doc_qa import DocumentIndex, DocumentQATool
from capabilities.reminders.scheduler import WorkflowScheduler
from capabilities.system.app_intel import AppIntelTool
from capabilities.system.input_control import ExplorerAutomationTool, InputControlTool
from capabilities.system.notification_guardian import NotificationGuardian, NotificationGuardianTool
from capabilities.system.security_guardian import SecurityGuardian, SecurityGuardianTool
from capabilities.system.ui_automation import UIActTool, UIFindTool
from capabilities.vision.screen_watch import ScreenWatchTool, compute_image_diff
from core.analytics.usage import UsageAnalytics
from core.model.router import CloudBlockedError, ModelRouter, RouterConfig
from core.tools.base import RiskLevel


@pytest.mark.asyncio
async def test_task_130_input_control() -> None:
    tool = InputControlTool()
    res_click = await tool.execute(action="click", x=100, y=200)
    assert res_click.status == "ok"
    assert "(100, 200)" in res_click.output

    res_hotkey = await tool.execute(action="hotkey", keys="ctrl+c")
    assert res_hotkey.status == "ok"
    assert "ctrl+c" in res_hotkey.output


@pytest.mark.asyncio
async def test_task_131_explorer_automation(tmp_path: Path) -> None:
    tool = ExplorerAutomationTool()
    res_new = await tool.execute(action="new_folder", path=str(tmp_path), folder_name="TestFolder")
    assert res_new.status == "ok"
    assert (tmp_path / "TestFolder").exists()


@pytest.mark.asyncio
async def test_task_132_app_intel() -> None:
    tool = AppIntelTool()
    res_set = await tool.execute(action="set_alias", alias="calc_shortcut", target="calc.exe")
    assert res_set.status == "ok"
    res_list = await tool.execute(action="list_aliases")
    assert res_list.status == "ok"
    assert "calc_shortcut" in res_list.output


@pytest.mark.asyncio
async def test_task_133_ui_find() -> None:
    tool = UIFindTool()
    res = await tool.execute(window_title="Notepad", control_name="File")
    assert res.status == "ok"
    assert "Found" in res.output


@pytest.mark.asyncio
async def test_task_134_ui_act_autonomous_loop() -> None:
    tool = UIActTool()
    # Safe sequence that completes and verifies
    steps = [
        {"action": "launch", "target": "notepad", "verify_expected": "notepad"},
        {"action": "type", "value": "hello world", "verify_expected": "hello world"},
        {"action": "wait"},
    ]
    res = await tool.execute(steps=steps)
    assert res.status == "ok"
    assert "Successfully executed 3 UI action steps" in res.output

    # Mismatch stops the loop immediately
    fail_steps = [
        {"action": "launch", "target": "notepad", "verify_expected": "missing_window"}
    ]
    res_fail = await tool.execute(steps=fail_steps)
    assert res_fail.status == "error"
    assert "Verification failed" in res_fail.error


@pytest.mark.asyncio
async def test_task_135_screen_watch() -> None:
    tool = ScreenWatchTool()
    # Run with small timeout to check graceful completion
    res = await tool.execute(x=0, y=0, width=50, height=50, timeout_s=0.5)
    assert res.status == "ok"


@pytest.mark.asyncio
async def test_task_136_shell_templates(tmp_path: Path) -> None:
    tool = ShellTemplateTool(sandbox_dir=tmp_path)
    # Test file listing in sandbox
    (tmp_path / "sandbox_test.txt").write_text("sample content")
    res = await tool.execute(template_name="cmd_dir", parameters={"options": ""})
    assert res.status == "ok"
    assert "sandbox_test.txt" in res.output

    # Prohibited injection character rejected
    res_inj = await tool.execute(template_name="cmd_dir", parameters={"options": "& calc.exe"})
    assert res_inj.status == "error"
    assert "Security violation" in res_inj.error


def test_task_137_security_guardian(tmp_path: Path) -> None:
    guardian = SecurityGuardian(quarantine_dir=tmp_path)
    mock_procs = [
        {"pid": 4040, "name": "badware.exe", "exe": "C:\\Users\\User\\AppData\\Local\\Temp\\badware.exe"},
        {"pid": 5050, "name": "notepad.exe", "exe": "C:\\Windows\\System32\\notepad.exe"},
    ]
    flagged = guardian.scan_processes(mock_procs)
    assert len(flagged) == 1
    assert flagged[0].pid == 4040

    # Unconfirmed quarantine refused
    refused = guardian.quarantine(4040, confirmed=False)
    assert refused["needs_confirmation"] is True

    # Confirmed quarantine executes
    confirmed = guardian.quarantine(4040, confirmed=True)
    assert confirmed["success"] is True


def test_task_138_notification_guardian() -> None:
    guardian = NotificationGuardian()
    tool = NotificationGuardianTool(guardian=guardian)
    # Checks either unsupported or off by default
    import asyncio
    res = asyncio.run(tool.execute(action="status"))
    assert res.status == "ok"
    assert "Notification Guardian" in res.output


def test_task_139_scheduler(tmp_path: Path) -> None:
    sched_file = tmp_path / "schedules.json"
    scheduler = WorkflowScheduler(storage_path=sched_file)

    # HIGH risk schedule strictly refused
    res_high = scheduler.schedule("job_high", "Dangerous", "w_del", "high", 60.0)
    assert res_high["success"] is False
    assert "HIGH-risk schedule refused" in res_high["error"]

    # Low risk schedule accepted and saved
    res_low = scheduler.schedule("job_low", "SafeSync", "w_sync", "low", 3600.0)
    assert res_low["success"] is True

    # Verify survival across restart
    scheduler_restarted = WorkflowScheduler(storage_path=sched_file)
    assert "job_low" in scheduler_restarted.jobs


@pytest.mark.asyncio
async def test_task_142_model_router() -> None:
    # Cloud blocked by default
    router_off = ModelRouter(config=RouterConfig(cloud_enabled=False))
    with pytest.raises(CloudBlockedError):
        await router_off.route_chat([], provider="openai")

    # Cloud permitted when enabled and logs payload
    router_on = ModelRouter(config=RouterConfig(cloud_enabled=True))
    res = await router_on.route_chat([], provider="openai")
    assert "Cloud Response" in res.content
    assert len(router_on.config.logged_payloads) == 1


def test_task_144_usage_analytics(tmp_path: Path) -> None:
    storage = tmp_path / "analytics.json"
    analytics = UsageAnalytics(storage_path=storage)
    analytics.record_tool_call("file.read", success=True, duration_s=0.1)
    analytics.record_tool_call("file.read", success=False, duration_s=0.2)
    analytics.record_tool_call("file.write", success=True, duration_s=0.3)

    report = analytics.get_report()
    assert report["total_calls"] == 3
    assert report["total_failures"] == 1
    assert report["tools"]["file.read"]["failure_rate_pct"] == 50.0


@pytest.mark.asyncio
async def test_task_145_doc_qa() -> None:
    index = DocumentIndex()
    index.index_document("financial_report.pdf", [
        "Executive Summary: Market trends in Q1.",
        "Revenue: Total quarterly revenue was $5.4 million.",
        "Conclusions and forward looking estimates.",
    ])
    tool = DocumentQATool(doc_index=index)
    res = await tool.execute(action="query", query="quarterly revenue")
    assert res.status == "ok"
    assert "[Source: financial_report.pdf, Page 2]" in res.output
    assert "$5.4 million" in res.output
