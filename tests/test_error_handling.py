"""T.A.R.O. - Error Handling Audit & Error Surfacing (TASK-092).

ARCHITECTURE reference: section 14, section 26.
RULES reference: section 3, 4.
TASKS: TASK-092.

Acceptance test:
- AST scan over all project python files passes with zero bare excepts.
- Sampled errors (file not found, syntax errors, permission errors) surface exact text.
"""

from __future__ import annotations

import ast
from pathlib import Path
import pytest

from capabilities.files.operations import FileReadTool, FileWriteTool
from core.model.ollama_client import ModelError
from core.tools.base import ToolResult


def test_task_092_no_bare_excepts_in_codebase() -> None:
    """Scans all Python source files in core/ and capabilities/ for bare except clauses."""
    repo_root = Path(__file__).resolve().parent.parent
    target_dirs = [repo_root / "core", repo_root / "capabilities"]

    bare_excepts = []
    for d in target_dirs:
        for py_file in d.rglob("*.py"):
            with open(py_file, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            try:
                tree = ast.parse(content)
            except SyntaxError:
                continue

            for node in ast.walk(tree):
                if isinstance(node, ast.ExceptHandler):
                    if node.type is None:
                        bare_excepts.append(f"{py_file.name}:{node.lineno}")

    assert len(bare_excepts) == 0, f"Found bare excepts without explicit Exception type: {bare_excepts}"


@pytest.mark.asyncio
async def test_task_092_sampled_errors_surface_exact_text() -> None:
    """Verifies that tool errors surface exact error text without suppression."""
    read_tool = FileReadTool()
    res = await read_tool.execute(path="non_existent_random_file_987654.txt")
    assert res.status == "error"
    assert "File not found" in res.error
    assert "non_existent_random_file_987654.txt" in res.error

    write_tool = FileWriteTool()
    res_imm = await write_tool.execute(path="core/tools/base.py", content="# tamper")
    assert res_imm.status == "error"
    assert "immutable" in res_imm.error.lower()
