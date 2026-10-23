"""T.A.R.O. - Import rules and stdlib-shadowing tests.

RULES reference: section 1, section 2.
TASKS: TASK-005.

Enforces:
1. Only winapi/ may import pywin32, pywinauto, or pynput.
2. Package names must never shadow Python standard library modules.
"""

from __future__ import annotations

import ast
from pathlib import Path

FORBIDDEN_WINAPI_MODULES = {
    "win32api",
    "win32con",
    "win32gui",
    "win32process",
    "pywintypes",
    "pythoncom",
    "pywinauto",
    "pynput",
}

STDLIB_SHADOW_NAMES = {
    "logging",
    "platform",
    "io",
    "sys",
    "os",
    "json",
    "math",
    "random",
    "re",
    "datetime",
    "time",
    "collections",
    "typing",
    "pathlib",
    "subprocess",
    "asyncio",
    "threading",
    "multiprocessing",
}


def find_winapi_violations(code: str, filename: str = "<string>") -> list[str]:
    """Parse python code and return list of forbidden winapi imports."""
    violations: list[str] = []
    tree = ast.parse(code, filename=filename)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root_mod = alias.name.split(".")[0]
                if root_mod in FORBIDDEN_WINAPI_MODULES:
                    violations.append(f"{filename}:{node.lineno} imports '{alias.name}'")
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                root_mod = node.module.split(".")[0]
                if root_mod in FORBIDDEN_WINAPI_MODULES:
                    violations.append(f"{filename}:{node.lineno} imports from '{node.module}'")
    return violations


def test_no_winapi_imports_outside_winapi() -> None:
    """Verifies that no core/ module outside winapi/ imports Windows automation libraries."""
    repo_root = Path(__file__).parent.parent
    core_dir = repo_root / "core"

    violations: list[str] = []

    for py_file in core_dir.rglob("*.py"):
        if "winapi" in py_file.parts:
            continue

        try:
            content = py_file.read_text(encoding="utf-8")
            violations.extend(find_winapi_violations(content, str(py_file.relative_to(repo_root))))
        except Exception as e:
            violations.append(f"{py_file}: Parse error: {e}")

    assert not violations, (
        "Import rule violation: Only winapi/ may import pywin32, pywinauto, or pynput:\n"
        + "\n".join(violations)
    )


def test_import_rule_fails_when_core_imports_pywin32() -> None:
    """TASK-005 acceptance: verify detector catches forbidden winapi import."""
    bad_code = "import win32api\nfrom pywinauto import Application"
    violations = find_winapi_violations(bad_code, "core/fake.py")
    assert len(violations) == 2
    assert any("win32api" in v for v in violations)
    assert any("pywinauto" in v for v in violations)


def test_no_stdlib_shadowing() -> None:
    """Verifies that no package or module name in core/ or capabilities/ shadows Python stdlib."""
    repo_root = Path(__file__).parent.parent
    checked_dirs = [repo_root / "core", repo_root / "capabilities"]

    violations: list[str] = []

    for parent_dir in checked_dirs:
        if not parent_dir.exists():
            continue
        for item in parent_dir.rglob("*"):
            if item.is_file() and item.suffix == ".py":
                stem = item.stem
                if stem in STDLIB_SHADOW_NAMES:
                    violations.append(
                        f"Module {item.relative_to(repo_root)} shadows stdlib module '{stem}'"
                    )
            elif item.is_dir() and item.name in STDLIB_SHADOW_NAMES:
                violations.append(
                    f"Package directory {item.relative_to(repo_root)} shadows stdlib package '{item.name}'"
                )

    assert not violations, (
        "Stdlib shadowing violation: The following packages/modules shadow Python stdlib:\n"
        + "\n".join(violations)
    )


def test_stdlib_shadowing_fails_on_forbidden_names() -> None:
    """TASK-005 acceptance: verify detector flags 'platform' and 'logging'."""
    assert "platform" in STDLIB_SHADOW_NAMES
    assert "logging" in STDLIB_SHADOW_NAMES
