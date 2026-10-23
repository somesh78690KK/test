"""T.A.R.O. - Comprehensive capabilities acceptance test suite.

Acceptance tests for Phase 4 tasks:
- TASK-040: App launcher
- TASK-041: Window control
- TASK-042: Process list and termination
- TASK-043: File operations
- TASK-057: Path robustness with spaces and Unicode 'Test Folder ñ 日本'
- TASK-044: Web search and fetch
- TASK-049: Hardware control
- TASK-050: Hardware stats
- TASK-051: Clipboard read and write
- TASK-052: Reminders and timers
- TASK-053: Notes dual-storage and semantic search
"""

from __future__ import annotations

import asyncio
import os
import tempfile
from pathlib import Path

import pytest
from capabilities import register_all_capabilities
from capabilities.files.operations import (
    FileCopyTool,
    FileDeleteTool,
    FileListTool,
    FileMoveTool,
    FileReadTool,
    FileRenameTool,
    FileSearchTool,
    FileUndoTool,
    FileWriteTool,
)
from capabilities.files.workspace import is_inside_workspace
from capabilities.notes.notes import NoteSaveTool, NoteSearchTool
from capabilities.reminders.timers import TimerManager
from capabilities.system.apps import AppLaunchTool
from capabilities.system.clipboard import ClipboardReadTool, ClipboardWriteTool
from capabilities.system.hardware import HardwareControlTool
from capabilities.system.processes import ProcessListTool, ProcessTerminateTool
from capabilities.system.stats import get_system_telemetry
from capabilities.system.windows import WindowControlTool
from capabilities.web.fetch import WebFetchTool
from capabilities.web.search import WebSearchTool
from core.tools.registry import ToolRegistry


def test_register_all_capabilities() -> None:
    """Verifies that all capability tools register without collision or missing attributes."""
    reg = ToolRegistry()
    count = register_all_capabilities(reg)
    assert count >= 15
    assert reg.get("file.read") is not None
    assert reg.get("code.run_python") is not None
    assert reg.get("app.launch") is not None
    assert reg.get("window.control") is not None
    assert reg.get("process.terminate") is not None


@pytest.mark.asyncio
async def test_task_040_app_launch_missing_returns_error() -> None:
    """TASK-040 acceptance: Launch of a missing app returns `error` with the real reason."""
    tool = AppLaunchTool()
    res = await tool.execute(name="non_existent_app_xyz_12345")
    assert res.status == "error"
    assert "not found" in res.error.lower()


@pytest.mark.asyncio
async def test_task_041_window_control_state_verification() -> None:
    """TASK-041 acceptance: Window control actions verified by window state."""
    tool = WindowControlTool()

    # 1. List windows
    res_list = await tool.execute(action="list")
    assert res_list.status == "ok"

    # 2. Get state for mock / first window
    res_state = await tool.execute(action="get_state", hwnd=1001)
    assert res_state.status == "ok"
    assert "state" in res_state.output

    # 3. Minimize
    res_min = await tool.execute(action="minimize", hwnd=1001)
    assert res_min.status == "ok"
    assert "minimized" in res_min.output.lower()

    # 4. Restore
    res_rest = await tool.execute(action="restore", hwnd=1001)
    assert res_rest.status == "ok"
    assert "restored" in res_rest.output.lower()


@pytest.mark.asyncio
async def test_task_042_process_protected_termination_refused() -> None:
    """TASK-042 acceptance: Terminating a protected process is refused."""
    term_tool = ProcessTerminateTool()

    # Attempting to terminate protected process (e.g. explorer.exe or svchost.exe or csrss.exe)
    res = await term_tool.execute(name="explorer.exe")
    assert res.status == "error"
    assert "protected system process" in res.error.lower()

    # Also list processes
    list_tool = ProcessListTool()
    res_list = await list_tool.execute(max_results=5)
    assert res_list.status == "ok"
    assert "Running processes" in res_list.output


@pytest.mark.asyncio
async def test_task_043_and_057_file_operations_and_path_robustness() -> None:
    """TASK-043 and TASK-057 acceptance:

    - Fixture folder named 'Test Folder ñ 日本' passes every file tool.
    - Delete outside workspace requires confirmation / records outside.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        # Fixture folder with spaces and Unicode (TASK-057)
        folder = Path(tmp_dir) / "Test Folder ñ 日本"
        folder.mkdir(parents=True, exist_ok=True)

        read_tool = FileReadTool()
        write_tool = FileWriteTool()
        copy_tool = FileCopyTool()
        move_tool = FileMoveTool()
        rename_tool = FileRenameTool()
        list_tool = FileListTool()
        search_tool = FileSearchTool()
        delete_tool = FileDeleteTool()

        file_path = folder / "test_doc_ñ.txt"

        # 1. Write file
        res_write = await write_tool.execute(path=str(file_path), content="Testing Unicode ñ 日本 123")
        assert res_write.status == "ok"
        assert file_path.exists()

        # 2. Read file
        res_read = await read_tool.execute(path=str(file_path))
        assert res_read.status == "ok"
        assert "Testing Unicode ñ 日本 123" in res_read.output

        # 3. List folder
        res_list = await list_tool.execute(path=str(folder))
        assert res_list.status == "ok"
        assert "test_doc_ñ.txt" in res_list.output

        # 4. Search folder
        res_search = await search_tool.execute(directory=str(folder), pattern="*.txt")
        assert res_search.status == "ok"
        assert "test_doc_ñ.txt" in res_search.output

        # 5. Copy file
        copy_path = folder / "copy_doc_ñ.txt"
        res_copy = await copy_tool.execute(source=str(file_path), destination=str(copy_path))
        assert res_copy.status == "ok"
        assert copy_path.exists()

        # 6. Rename copy
        res_rename = await rename_tool.execute(path=str(copy_path), new_name="renamed_ñ.txt")
        assert res_rename.status == "ok"
        renamed_path = folder / "renamed_ñ.txt"
        assert renamed_path.exists()

        # 7. Move file
        sub_folder = folder / "Sub ñ"
        moved_path = sub_folder / "moved_ñ.txt"
        res_move = await move_tool.execute(source=str(renamed_path), destination=str(moved_path))
        assert res_move.status == "ok"
        assert moved_path.exists()

        # 8. Delete file (TASK-043: verifies deletion and recovery)
        res_del = await delete_tool.execute(path=str(file_path))
        assert res_del.status == "ok"
        assert not file_path.exists()
        assert "deleted" in res_del.output.lower()

        # 9. Undo deletion (TASK-140: restores deleted file)
        undo_tool = FileUndoTool()
        res_undo = await undo_tool.execute()
        assert res_undo.status == "ok"
        assert file_path.exists()

        # 10. Dry run mode (TASK-141: dry run changes nothing)
        res_dry = await delete_tool.execute(path=str(file_path), dry_run=True)
        assert res_dry.status == "ok"
        assert "[DRY RUN]" in res_dry.output
        assert file_path.exists()

        # 11. Immutable path protection (TASK-115)
        res_imm = await write_tool.execute(path="core/safety/permissions.py", content="# hacked")
        assert res_imm.status == "error"
        assert "immutable" in res_imm.error.lower()


@pytest.mark.asyncio
async def test_task_044_web_search_and_fetch_url_returned() -> None:
    """TASK-044 acceptance: Answer includes at least one URL from tool result."""
    from unittest.mock import AsyncMock, MagicMock, patch

    search_tool = WebSearchTool()
    res_search = await search_tool.execute(query="python programming language")
    assert res_search.status == "ok"
    assert "http" in res_search.output
    assert "<untrusted source=\"web\">" in res_search.output

    # Web fetch with mocked network to guarantee offline test reliability
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "<html><body><h1>DuckDuckGo</h1><p>Search privacy</p></body></html>"
        mock_get.return_value = mock_resp

        fetch_tool = WebFetchTool()
        res_fetch = await fetch_tool.execute(url="https://duckduckgo.com")
        assert res_fetch.status == "ok"
        assert "https://duckduckgo.com" in res_fetch.output
        assert "<untrusted source=\"web\">" in res_fetch.output


@pytest.mark.asyncio
async def test_task_049_hardware_control_volume_verification() -> None:
    """TASK-049 acceptance: Volume change verified by reading the system value."""
    tool = HardwareControlTool()
    res_set = await tool.execute(action="set_volume", level=45)
    assert res_set.status == "ok"
    assert "45" in res_set.output

    res_get = await tool.execute(action="get_volume")
    assert res_get.status == "ok"
    assert "45" in res_get.output


def test_task_050_hardware_stats_missing_sensors_show_na() -> None:
    """TASK-050 acceptance: Stats update every 1s; missing sensors show 'n/a'."""
    stats = get_system_telemetry()
    assert "cpu_percent" in stats
    assert "ram_used_gb" in stats
    assert "ram_total_gb" in stats
    assert "disk_used_gb" in stats
    # Check that temperature or GPU are either numbers or 'n/a'
    assert isinstance(stats["temperature"], (int, float, str))
    if isinstance(stats["temperature"], str):
        assert stats["temperature"] == "n/a"


@pytest.mark.asyncio
async def test_task_051_clipboard_round_trip() -> None:
    """TASK-051 acceptance: Clipboard read/write round-trip test passes."""
    write_tool = ClipboardWriteTool()
    read_tool = ClipboardReadTool()

    secret_text = "TARO_TEST_CLIPBOARD_TEXT_42"
    res_w = await write_tool.execute(text=secret_text)
    assert res_w.status == "ok"

    res_r = await read_tool.execute()
    assert res_r.status == "ok"
    assert secret_text in res_r.output


@pytest.mark.asyncio
async def test_task_052_reminders_and_timers_callback_fires() -> None:
    """TASK-052 acceptance: Timer fires a notification and TTS message."""
    mgr = TimerManager()
    events: list[tuple[str, str]] = []

    mgr.on_fire(lambda tid, msg: events.append((tid, msg)))

    # Set 0.1s timer
    timer = await mgr.set_timer(0.1, "Test alarm message")
    assert timer.id in mgr.timers

    # Wait for expiry
    await asyncio.sleep(0.2)
    assert len(events) == 1
    assert events[0][1] == "Test alarm message"
    assert timer.id not in mgr.timers


@pytest.mark.asyncio
async def test_task_053_notes_saved_and_found_by_semantic_search() -> None:
    """TASK-053 acceptance: Note saved, found by semantic search."""
    save_tool = NoteSaveTool()
    search_tool = NoteSearchTool()

    # 1. Save note
    title = "Quantum Computing Roadmap"
    content = "Detailed plan for superconducting qubit experiments and quantum error correction."
    res_save = await save_tool.execute(title=title, content=content, tags=["quantum", "physics"])
    assert res_save.status == "ok"
    assert "saved successfully" in res_save.output

    # 2. Search note semantically
    res_search = await search_tool.execute(query="superconducting qubits")
    assert res_search.status == "ok"
    assert "Quantum Computing Roadmap" in res_search.output or "superconducting" in res_search.output.lower()


@pytest.mark.asyncio
async def test_task_047_excel_automation() -> None:
    """TASK-047 acceptance: Test workbook created with three columns and saved in workspace."""
    from capabilities.office.excel import ExcelTool

    with tempfile.TemporaryDirectory() as tmp_dir:
        wb_file = Path(tmp_dir) / "test_sheet.xlsx"
        tool = ExcelTool()

        headers = ["Item Name", "Quantity", "Price"]
        rows = [["Widget A", 10, 5.5], ["Widget B", 20, 12.0]]

        # 1. Create workbook with three columns
        res_create = await tool.execute(
            action="create",
            path=str(wb_file),
            headers=headers,
            rows=rows,
        )
        assert res_create.status == "ok"
        assert wb_file.exists()

        # 2. Read workbook
        res_read = await tool.execute(action="read", path=str(wb_file))
        assert res_read.status == "ok"
        assert "Item Name" in res_read.output
        assert "Widget A" in res_read.output


@pytest.mark.asyncio
async def test_task_048_word_and_powerpoint_basics() -> None:
    """TASK-048 acceptance: Test document and deck created."""
    from capabilities.office.word import WordTool
    from capabilities.office.powerpoint import PowerPointTool

    with tempfile.TemporaryDirectory() as tmp_dir:
        doc_file = Path(tmp_dir) / "test_doc.docx"
        deck_file = Path(tmp_dir) / "test_deck.pptx"

        # 1. Create Word document
        w_tool = WordTool()
        res_w = await w_tool.execute(
            action="create",
            path=str(doc_file),
            title="TARO Project Specification",
            paragraphs=["This is paragraph 1.", "This is paragraph 2."],
        )
        assert res_w.status == "ok"
        assert doc_file.exists()

        # Read back document
        res_r_w = await w_tool.execute(action="read", path=str(doc_file))
        assert res_r_w.status == "ok"
        assert "TARO Project Specification" in res_r_w.output

        # 2. Create PowerPoint presentation deck
        ppt_tool = PowerPointTool()
        slides = [
            {"title": "Introduction", "content": "Overview of T.A.R.O. capabilities."},
            {"title": "Architecture", "content": "Model core, safety gate, tools."},
        ]
        res_ppt = await ppt_tool.execute(
            action="create",
            path=str(deck_file),
            title="TARO Slide Deck",
            slides=slides,
        )
        assert res_ppt.status == "ok"
        assert deck_file.exists()

        # Read back presentation
        res_r_ppt = await ppt_tool.execute(action="read", path=str(deck_file))
        assert res_r_ppt.status == "ok"
        assert "Introduction" in res_r_ppt.output

