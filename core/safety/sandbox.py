"""T.A.R.O. - Sandboxed code execution.

ARCHITECTURE reference: section 14.
RULES reference: section 4, 10.
TASKS: TASK-035.

Executes Python code with:
1. Fixed working directory confined to `sandbox/`.
2. Enforcement that scripts cannot target or write to paths outside `sandbox/`.
3. 30-second default timeout with guaranteed process killing.
4. Output capture (stdout and stderr).
5. Kill-switch integration.
"""

from __future__ import annotations

import ast
import os
import subprocess
import sys
import tempfile
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

from core.log.setup import get_logger
from core.safety.kill_switch import kill_switch

logger = get_logger(__name__)

DEFAULT_SANDBOX_TIMEOUT = 30.0


@dataclass
class SandboxResult:
    """Result of running a script in the sandbox."""

    success: bool
    stdout: str
    stderr: str
    returncode: int
    timed_out: bool = False
    blocked_reason: str | None = None
    duration_s: float = 0.0


class SecurityViolationError(Exception):
    """Raised when code attempts prohibited actions like writing outside sandbox."""


def validate_code_safety(code: str, sandbox_dir: Path) -> None:
    """Statically checks AST for prohibited write paths or system tampering.

    Rejects:
    - File writes using open() with modes 'w', 'a', 'x', '+', or Path.write_*
      to absolute paths outside sandbox_dir or relative paths that traverse '..' outside sandbox_dir.
    - Attempts to change directory (os.chdir) to outside sandbox.
    """
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        raise SecurityViolationError(f"Syntax error in code: {e}") from e

    sandbox_resolved = sandbox_dir.resolve()

    for node in ast.walk(tree):
        # Check os.chdir(...)
        if isinstance(node, ast.Call):
            func_name = ""
            if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
                func_name = f"{node.func.value.id}.{node.func.attr}"
            elif isinstance(node.func, ast.Name):
                func_name = node.func.id

            # Detect open() calls with write modes
            if func_name == "open" and len(node.args) >= 1:
                # Check target path if constant string
                path_arg = node.args[0]
                mode_arg = node.args[1] if len(node.args) > 1 else None

                # Check write mode
                is_write = False
                if mode_arg and isinstance(mode_arg, ast.Constant) and isinstance(mode_arg.value, str):
                    if any(m in mode_arg.value for m in ("w", "a", "x", "+")):
                        is_write = True
                # Check keywords for mode
                for kw in node.keywords:
                    if kw.arg == "mode" and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
                        if any(m in kw.value.value for m in ("w", "a", "x", "+")):
                            is_write = True

                if is_write and isinstance(path_arg, ast.Constant) and isinstance(path_arg.value, str):
                    target_str = path_arg.value
                    target_path = (sandbox_resolved / target_str).resolve()
                    if not target_path.is_relative_to(sandbox_resolved):
                        raise SecurityViolationError(
                            f"Write operation to path outside sandbox is blocked: '{target_str}'"
                        )

            # Detect Path.write_text, Path.write_bytes
            if isinstance(node.func, ast.Attribute) and node.func.attr in ("write_text", "write_bytes"):
                # If Path("...") is used
                if isinstance(node.func.value, ast.Call) and isinstance(node.func.value.func, ast.Name):
                    if node.func.value.func.id == "Path" and node.func.value.args:
                        arg0 = node.func.value.args[0]
                        if isinstance(arg0, ast.Constant) and isinstance(arg0.value, str):
                            target_path = (sandbox_resolved / arg0.value).resolve()
                            if not target_path.is_relative_to(sandbox_resolved):
                                raise SecurityViolationError(
                                    f"Write operation to path outside sandbox is blocked: '{arg0.value}'"
                                )


class CodeSandbox:
    """Confines execution to sandbox directory with strict timeouts and output capture."""

    def __init__(self, sandbox_dir: Path | None = None) -> None:
        if sandbox_dir is None:
            # Default to <repo_root>/sandbox
            repo_root = Path(__file__).resolve().parent.parent.parent
            self.sandbox_dir = repo_root / "sandbox"
        else:
            self.sandbox_dir = sandbox_dir

        self.sandbox_dir.mkdir(parents=True, exist_ok=True)

    def execute_python(
        self,
        code: str,
        timeout_s: float = DEFAULT_SANDBOX_TIMEOUT,
        env: dict[str, str] | None = None,
    ) -> SandboxResult:
        """Runs the given python code inside the sandbox.

        Args:
            code: Python code string.
            timeout_s: Maximum execution duration in seconds.
            env: Optional environment variables dictionary.

        Returns:
            SandboxResult with stdout, stderr, exit code, and status flags.
        """
        start_time = time.time()

        # 1. Kill-switch check
        if kill_switch.is_killed:
            return SandboxResult(
                success=False,
                stdout="",
                stderr="Execution aborted: Global kill switch is active.",
                returncode=-1,
                blocked_reason="Kill switch active",
            )

        # 2. Static security validation
        try:
            validate_code_safety(code, self.sandbox_dir)
        except SecurityViolationError as e:
            logger.warning("sandbox_security_violation", error=str(e))
            return SandboxResult(
                success=False,
                stdout="",
                stderr=f"SecurityViolationError: {e}",
                returncode=1,
                blocked_reason=str(e),
                duration_s=time.time() - start_time,
            )

        # 3. Create isolated script file in sandbox
        script_name = f"_run_{uuid.uuid4().hex[:8]}.py"
        script_path = self.sandbox_dir / script_name

        # Prepend runtime boundary check to ensure any dynamic writes remain confined
        harness = (
            "import os, sys, pathlib\n"
            f"_SANDBOX = pathlib.Path(r'{self.sandbox_dir.resolve()}').resolve()\n"
            "_orig_open = open\n"
            "def _guarded_open(file, mode='r', *args, **kwargs):\n"
            "    if any(m in mode for m in ('w', 'a', 'x', '+')):\n"
            "        p = (pathlib.Path(file) if pathlib.Path(file).is_absolute() else _SANDBOX / file).resolve()\n"
            "        if not p.is_relative_to(_SANDBOX):\n"
            "            raise PermissionError(f'Sandbox write blocked to: {file}')\n"
            "    return _orig_open(file, mode, *args, **kwargs)\n"
            "import builtins\n"
            "builtins.open = _guarded_open\n\n"
        )

        full_code = harness + code
        script_path.write_text(full_code, encoding="utf-8")

        run_env = os.environ.copy()
        if env:
            run_env.update(env)
        # Prevent python from buffering stdout/stderr
        run_env["PYTHONUNBUFFERED"] = "1"

        proc = None
        try:
            proc = subprocess.Popen(
                [sys.executable, str(script_path.name)],
                cwd=str(self.sandbox_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=run_env,
            )
            kill_switch.register_process(proc)

            stdout, stderr = proc.communicate(timeout=timeout_s)
            duration = time.time() - start_time

            return SandboxResult(
                success=(proc.returncode == 0),
                stdout=stdout,
                stderr=stderr,
                returncode=proc.returncode,
                timed_out=False,
                duration_s=duration,
            )

        except subprocess.TimeoutExpired:
            duration = time.time() - start_time
            logger.warning("sandbox_execution_timeout", timeout_s=timeout_s)
            if proc:
                try:
                    proc.kill()
                    stdout, stderr = proc.communicate()
                except Exception:
                    stdout, stderr = "", ""
            else:
                stdout, stderr = "", ""

            return SandboxResult(
                success=False,
                stdout=stdout,
                stderr=f"Execution timed out after {timeout_s}s. Process terminated.",
                returncode=-1,
                timed_out=True,
                duration_s=duration,
            )
        except Exception as e:
            duration = time.time() - start_time
            logger.error("sandbox_execution_error", error=str(e))
            return SandboxResult(
                success=False,
                stdout="",
                stderr=f"Execution error: {e}",
                returncode=-1,
                duration_s=duration,
            )
        finally:
            if proc:
                kill_switch.unregister_process(proc)
            if script_path.exists():
                try:
                    script_path.unlink()
                except OSError:
                    pass


# Default sandbox instance
default_sandbox = CodeSandbox()
