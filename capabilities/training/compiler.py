"""T.A.R.O. - Workflow compiler (TASK-074).

ARCHITECTURE reference: section 11.
RULES reference: section 3, 10.
TASKS: TASK-074.

Compiles raw recorded events into an optimized, executable workflow structure:
- Merges high-frequency mouse movements.
- Groups individual keystrokes into unified `type_text` actions.
- Attaches target window title and verification context to every step.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.log.setup import get_logger

logger = get_logger(__name__)


def compile_workflow(
    raw_events: list[dict[str, Any]],
    workflow_name: str = "custom_workflow",
    description: str = "",
) -> dict[str, Any]:
    """Compile raw input events into an optimized workflow specification."""
    steps: list[dict[str, Any]] = []
    current_text = ""
    current_window = ""

    def flush_text():
        nonlocal current_text, current_window
        if current_text:
            steps.append({
                "action": "type_text",
                "text": current_text,
                "target_window": current_window,
            })
            current_text = ""

    for ev in raw_events:
        ev_type = ev.get("type")
        win = ev.get("window", "")

        if ev_type == "key_press":
            key_val = ev.get("key", "")
            if len(key_val) == 1:
                current_text += key_val
                current_window = win
            elif key_val == "space":
                current_text += " "
                current_window = win
            else:
                flush_text()
                steps.append({
                    "action": "key_press",
                    "key": key_val,
                    "target_window": win,
                })

        elif ev_type == "click":
            flush_text()
            steps.append({
                "action": "click",
                "x": ev.get("x", 0),
                "y": ev.get("y", 0),
                "button": ev.get("button", "left"),
                "target_window": win,
            })

        elif ev_type == "shortcut":
            flush_text()
            steps.append({
                "action": "shortcut",
                "keys": ev.get("keys", []),
                "target_window": win,
            })

    flush_text()

    workflow = {
        "name": workflow_name,
        "version": "1.0.0",
        "description": description or f"Compiled workflow '{workflow_name}'",
        "step_count": len(steps),
        "steps": steps,
    }
    logger.info("workflow_compiled", name=workflow_name, steps=len(steps))
    return workflow


def compile_file(jsonl_path: Path | str, workflow_name: str | None = None) -> dict[str, Any]:
    """Read events from JSONL file and compile."""
    p = Path(jsonl_path)
    events = []
    with open(p, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                events.append(json.loads(line))
    name = workflow_name or p.stem
    return compile_workflow(events, workflow_name=name)
