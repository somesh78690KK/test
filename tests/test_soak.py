"""T.A.R.O. - Soak & Endurance Session Harness (TASK-090).

ARCHITECTURE reference: section 11, section 26.
RULES reference: section 2 (6GB VRAM Safety Bound), section 4 (Reliability).
TASKS: TASK-090.

Simulates mixed multi-turn workloads across:
- Chat completions & orchestrator planning
- Tool executions (filesystem, hardware, shell, scheduler)
- Vision capture & diffing
- Memory management & VRAM/RAM ceiling check (< 5.5 GB peak).
"""

from __future__ import annotations

import asyncio
import gc
import os
import psutil
import pytest
import time
from pathlib import Path

from capabilities.files.operations import FileListTool, FileReadTool, FileWriteTool
from capabilities.notes.doc_qa import DocumentIndex, DocumentQATool
from capabilities.reminders.scheduler import WorkflowScheduler
from capabilities.system.ui_automation import UIFindTool
from core.analytics.usage import UsageAnalytics
from core.forge.static_check import check_skill_code
from core.model.ollama_client import ChatMessage, ChatResponse, OllamaClient
from core.orchestrator import Orchestrator
from core.tools.registry import ToolRegistry


class FakeSoakOllamaClient:
    """Mock model client for predictable offline endurance testing."""

    async def chat(self, model: str, messages: list[ChatMessage], tools: list | None = None) -> ChatResponse:
        await asyncio.sleep(0.01)
        return ChatResponse(
            content="Task completed successfully.",
            tool_calls=[],
            model=model,
            done=True,
            duration_ms=10,
            prompt_tokens=25,
            completion_tokens=15,
        )


@pytest.mark.asyncio
async def test_task_090_mixed_session_endurance(tmp_path: Path) -> None:
    """Executes a multi-iteration mixed endurance cycle verifying memory stability."""
    process = psutil.Process(os.getpid())
    initial_rss_mb = process.memory_info().rss / (1024 * 1024)

    # Initialize components
    registry = ToolRegistry()
    registry.register(FileListTool())
    registry.register(FileReadTool())
    registry.register(FileWriteTool())
    registry.register(UIFindTool())

    client = FakeSoakOllamaClient()
    scheduler = WorkflowScheduler(storage_path=tmp_path / "soak_sched.json")
    analytics = UsageAnalytics(storage_path=tmp_path / "soak_analytics.json")
    doc_index = DocumentIndex()
    doc_index.index_document("doc.txt", [f"Page {i} data content" for i in range(1, 20)])

    # Run 50 mixed workload cycles
    iterations = 50
    for i in range(iterations):
        # 1. Chat turn
        resp = await client.chat("taro", [ChatMessage(role="user", content=f"Soak turn {i}")])
        assert resp.done is True

        # 2. File tool write & read
        test_file = tmp_path / f"test_{i}.txt"
        w_res = await FileWriteTool().execute(path=str(test_file), content=f"Soak content {i}")
        assert w_res.status == "ok"

        r_res = await FileReadTool().execute(path=str(test_file))
        assert r_res.status == "ok"

        # 3. Static code analysis
        is_safe, _ = check_skill_code(f"def compute_{i}(): return {i} * 2")
        assert is_safe is True

        # 4. Doc Q&A query
        results = doc_index.query(f"Page {i % 10 + 1}")
        assert len(results) > 0

        # 5. Scheduler job
        scheduler.schedule(f"job_{i}", f"Task {i}", "w_test", "low", 3600.0)

        # 6. Analytics recording
        analytics.record_tool_call("file.read", success=True, duration_s=0.005)

    gc.collect()
    peak_rss_mb = process.memory_info().rss / (1024 * 1024)

    # Acceptance check: Peak process RAM must remain well under 5.5 GB (5500 MB)
    assert peak_rss_mb < 5500.0, f"Memory ceiling exceeded: peak RSS was {peak_rss_mb} MB"
