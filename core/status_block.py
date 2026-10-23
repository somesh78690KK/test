"""T.A.R.O. - Code-generated status block formatter (TASK-023).

ARCHITECTURE reference: section 7.
RULES reference: section 3.
TASKS: TASK-023.

Generates the deterministic status block from code and tool results.
The model's prose cannot edit or fabricate this block.
"""

from __future__ import annotations

from typing import Any


def format_status_block(tool_entries: list[tuple[str, Any]]) -> str:
    """Format list of (tool_name, result) into a deterministic monospace status block.

    Acceptance (TASK-023):
    A turn where a tool errors and the model says "done" still shows FAILED
    with the real error in the status block.
    """
    if not tool_entries:
        return ""

    lines = []
    for name, res in tool_entries:
        if hasattr(res, "to_status_line"):
            lines.append(res.to_status_line(name))
        elif isinstance(res, dict):
            status = res.get("status", "ok").upper()
            err = res.get("error", "")
            if status == "OK":
                lines.append(f"{name}: OK")
            elif status == "DENIED":
                lines.append(f"{name}: DENIED - {err}")
            else:
                lines.append(f"{name}: FAILED - {err}")
        else:
            lines.append(f"{name}: OK")

    return "\n".join(lines)
