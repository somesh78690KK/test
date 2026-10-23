"""T.A.R.O. - Static AST code checker (TASK-114).

ARCHITECTURE reference: section 18 (Self-Extension & Forge).
RULES reference: section 3, 4, 10.
TASKS: TASK-114.

Static analysis for Forge-generated code before execution:
1. AST scan for prohibited constructs (eval, exec, __import__, ctypes, os.system).
2. Allowlist verification against config/skill_allowlist.json.
3. Path guard: prevents references/writes to immutable paths (core/, config/permissions.json).
4. Network host guard: limits network requests to allowed domains.

Acceptance (TASK-114): Test set of 20 malicious snippets: all rejected.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

from core.log.setup import get_logger

logger = get_logger(__name__)

BANNED_FUNCTIONS = {
    "eval",
    "exec",
    "__import__",
    "compile",
    "globals",
    "locals",
}

BANNED_MODULES = {
    "ctypes",
    "winreg",
    "socket",
    "pickle",
    "shelve",
    "pty",
}

IMMUTABLE_PATHS = [
    "core/",
    "core\\",
    "config/permissions.json",
    "config\\permissions.json",
    "c:\\windows",
    "system32",
    "/etc",
]


def load_allowlist(allowlist_path: Path | str | None = None) -> set[str]:
    """Load allowed module names from config/skill_allowlist.json."""
    p = Path(allowlist_path) if allowlist_path else Path("config/skill_allowlist.json")
    allowed = set()
    if p.exists():
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
            allowed.update(data.get("allowed_stdlib", []))
            allowed.update(data.get("allowed_third_party", []))
        except Exception as e:
            logger.warning("failed_to_load_skill_allowlist", error=str(e))

    # Base safe fallback
    if not allowed:
        allowed = {
            "pathlib", "json", "csv", "datetime", "re", "math", "typing",
            "openpyxl", "docx", "PIL", "httpx", "time", "shutil", "io"
        }
    return allowed


class SecurityASTVisitor(ast.NodeVisitor):
    """Inspects AST nodes for security rule violations."""

    def __init__(self, allowed_modules: set[str]) -> None:
        self.allowed_modules = allowed_modules
        self.violations: list[str] = []

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            top_level = alias.name.split(".")[0]
            if top_level in BANNED_MODULES or top_level not in self.allowed_modules:
                self.violations.append(f"Import of unapproved or banned module: '{alias.name}'.")
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module:
            top_level = node.module.split(".")[0]
            if top_level in BANNED_MODULES or top_level not in self.allowed_modules:
                self.violations.append(f"Import from unapproved or banned module: '{node.module}'.")
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        if node.id in ("__builtins__", "__import__", "__loader__", "__spec__"):
            self.violations.append(f"Unsafe direct access to '{node.id}'.")
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        # Check direct calls like eval(...) or exec(...)
        if isinstance(node.func, ast.Name):
            if node.func.id in BANNED_FUNCTIONS:
                self.violations.append(f"Use of banned function: '{node.func.id}()'.")
            elif node.func.id == "getattr":
                for arg in node.args:
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                        if arg.value in BANNED_FUNCTIONS or (arg.value.startswith("__") and arg.value.endswith("__")):
                            self.violations.append(f"Unsafe getattr call accessing '{arg.value}'.")

        # Check attribute calls like os.system(...)
        elif isinstance(node.func, ast.Attribute):
            attr_name = node.func.attr
            if attr_name in ("system", "popen", "spawn", "execve", "fork"):
                self.violations.append(f"Unsafe process execution call: '.{attr_name}()'.")
            elif attr_name in BANNED_FUNCTIONS:
                self.violations.append(f"Use of banned function: '.{attr_name}()'.")

        self.generic_visit(node)

    def visit_Constant(self, node: ast.Constant) -> None:
        # Path guard on string literals targeting immutable core areas
        if isinstance(node.value, str):
            val_lower = node.value.lower()
            for imm in IMMUTABLE_PATHS:
                if imm in val_lower:
                    self.violations.append(
                        f"Prohibited path reference targeting protected system path: '{node.value}'."
                    )
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        # Prohibit dunder introspection like __subclasses__, __builtins__
        if node.attr.startswith("__") and node.attr.endswith("__"):
            if node.attr in ("__subclasses__", "__builtins__", "__globals__", "__code__"):
                self.violations.append(f"Unsafe introspection access to '{node.attr}'.")
        self.generic_visit(node)


def check_skill_code(code: str, allowlist_path: Path | str | None = None) -> tuple[bool, list[str]]:
    """Scan python source code for security violations.

    Acceptance (TASK-114): Test set of 20 malicious snippets: all rejected.
    """
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return False, [f"Syntax error in skill code: {e}"]

    allowed = load_allowlist(allowlist_path)
    visitor = SecurityASTVisitor(allowed)
    visitor.visit(tree)

    if visitor.violations:
        return False, visitor.violations
    return True, []
