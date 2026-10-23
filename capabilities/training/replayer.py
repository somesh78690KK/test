"""T.A.R.O. - Workflow replayer with per-step verification (TASK-075).

ARCHITECTURE reference: section 11.
RULES reference: section 4, 10.
TASKS: TASK-075.

Replays compiled workflows with strict safety validation:
- Checks the active foreground window title before every step.
- ABORTS immediately if the foreground window does not match the expected context.
- Records success/failure metrics.
"""

from __future__ import annotations

import asyncio
from typing import Any, Callable

from core.log.setup import get_logger

logger = get_logger(__name__)


def get_default_active_window() -> str:
    """Read active window title using winapi helper if available."""
    try:
        from winapi.window_ops import get_foreground_window_title
        return get_foreground_window_title()
    except Exception:
        return "Unknown"


class WorkflowReplayer:
    """Executes workflow steps while verifying environment state at each step."""

    def __init__(
        self,
        get_active_window_func: Callable[[], str] | None = None,
        step_executor: Callable[[dict[str, Any]], Any] | None = None,
    ) -> None:
        self.get_active_window = get_active_window_func or get_default_active_window
        self.step_executor = step_executor

    async def replay(self, workflow: dict[str, Any]) -> dict[str, Any]:
        """Replay all steps in the workflow with per-step window verification.

        Acceptance (TASK-075): Replay stops on window mismatch.
        """
        name = workflow.get("name", "unnamed")
        steps = workflow.get("steps", [])
        completed = 0

        logger.info("workflow_replay_started", name=name, total_steps=len(steps))

        for idx, step in enumerate(steps):
            expected_window = step.get("target_window", "")
            if expected_window:
                current_window = self.get_active_window()
                # Check if current window matches expected (fuzzy or substring check)
                if expected_window.lower() not in current_window.lower():
                    err_msg = (
                        f"Replay halted at step {idx + 1}: Window mismatch. "
                        f"Expected '{expected_window}', but active window is '{current_window}'."
                    )
                    logger.warning("workflow_window_mismatch", step=idx + 1, error=err_msg)
                    return {
                        "status": "failed",
                        "workflow": name,
                        "completed_steps": completed,
                        "total_steps": len(steps),
                        "error": err_msg,
                    }

            # Execute step
            try:
                if self.step_executor:
                    res = self.step_executor(step)
                    if asyncio.iscoroutine(res):
                        await res
                await asyncio.sleep(0.05)  # brief pause between actions
                completed += 1
            except Exception as e:
                err_msg = f"Step {idx + 1} execution failed: {e}"
                logger.error("workflow_step_error", step=idx + 1, error=str(e))
                return {
                    "status": "failed",
                    "workflow": name,
                    "completed_steps": completed,
                    "total_steps": len(steps),
                    "error": err_msg,
                }

        logger.info("workflow_replay_completed", name=name, steps=completed)
        return {
            "status": "ok",
            "workflow": name,
            "completed_steps": completed,
            "total_steps": len(steps),
            "output": f"Successfully replayed all {completed} steps.",
        }
