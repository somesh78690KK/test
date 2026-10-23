"""T.A.R.O. - Out-of-process Skill Host (TASK-124).

ARCHITECTURE reference: section 18.
RULES reference: section 4, 10.
TASKS: TASK-124.

Executes skills in an isolated subprocess:
- Sanitizes environment: strips core API keys (OPENAI_API_KEY, GEMINI_API_KEY, etc.).
- Limits runtime with hard timeout.
- Captures output and returns structured execution dictionary.

Acceptance (TASK-124):
- Skill cannot read the core's API keys.
- Runaway skill is killed at its limit.
- Killing the core kills the host.
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from core.log.setup import get_logger

logger = get_logger(__name__)

# Keys stripped from the subprocess environment for security
SENSITIVE_ENV_VARS = {
    "OPENAI_API_KEY",
    "GEMINI_API_KEY",
    "ANTHROPIC_API_KEY",
    "GROQ_API_KEY",
    "AWS_SECRET_ACCESS_KEY",
    "TARO_SESSION_TOKEN",
    "API_KEY",
    "SECRET",
}


def create_sanitized_env() -> dict[str, str]:
    """Return a clean copy of os.environ without any secret API keys."""
    clean_env = dict(os.environ)
    for key in list(clean_env.keys()):
        upper = key.upper()
        if any(sens in upper for sens in SENSITIVE_ENV_VARS) or "TOKEN" in upper or "KEY" in upper:
            clean_env.pop(key, None)
    return clean_env


async def run_skill_in_host(
    skill_script_path: Path | str,
    args: dict[str, Any],
    timeout_s: float = 30.0,
) -> dict[str, Any]:
    """Execute a skill script in a child process with sanitized environment."""
    script_p = Path(skill_script_path).resolve()
    if not script_p.exists():
        return {"status": "error", "error": f"Script not found: {script_p}"}

    # Runner harness code
    runner_code = f"""
import sys
import json
from pathlib import Path

# Add script folder to path
sys.path.insert(0, str(Path(r'{script_p.parent}')))
import {script_p.stem} as skill_mod

args = json.loads({json.dumps(json.dumps(args))})
try:
    res = skill_mod.run(args)
    if isinstance(res, dict):
        print("TARO_SKILL_RESULT:" + json.dumps(res))
    else:
        print("TARO_SKILL_RESULT:" + json.dumps({{"status": "ok", "output": str(res)}}))
except Exception as e:
    print("TARO_SKILL_RESULT:" + json.dumps({{"status": "error", "error": str(e)}}))
"""

    clean_env = create_sanitized_env()
    start = time.monotonic()

    try:
        proc = await asyncio.create_subprocess_exec(
            sys.executable,
            "-c",
            runner_code,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=clean_env,
        )

        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(proc.communicate(), timeout=timeout_s)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            return {
                "status": "error",
                "error": f"Skill execution exceeded {timeout_s}s timeout limit.",
                "duration_ms": int((time.monotonic() - start) * 1000),
            }

        elapsed_ms = int((time.monotonic() - start) * 1000)
        stdout = stdout_bytes.decode("utf-8", errors="replace")
        stderr = stderr_bytes.decode("utf-8", errors="replace")

        # Extract structured result
        for line in stdout.splitlines():
            if line.startswith("TARO_SKILL_RESULT:"):
                payload = line[len("TARO_SKILL_RESULT:"):].strip()
                result_dict = json.loads(payload)
                result_dict["duration_ms"] = elapsed_ms
                return result_dict

        if proc.returncode != 0:
            return {
                "status": "error",
                "error": f"Subprocess exited with code {proc.returncode}: {stderr or stdout}",
                "duration_ms": elapsed_ms,
            }

        return {"status": "ok", "output": stdout.strip(), "duration_ms": elapsed_ms}

    except Exception as e:
        logger.error("skill_host_error", script=str(script_p), error=str(e))
        return {"status": "error", "error": f"Host execution error: {e}"}
