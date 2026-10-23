"""Execution template for file skills."""

from pathlib import Path
from typing import Any


def run(args: dict[str, Any]) -> dict[str, Any]:
    filepath = args.get("filepath", "")
    p = Path(filepath)
    if not p.exists():
        return {"status": "error", "error": f"File not found: {filepath}"}

    return {"status": "ok", "output": f"Processed file: {p.name} ({p.stat().st_size} bytes)"}
