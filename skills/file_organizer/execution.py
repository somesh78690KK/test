"""Execution logic for file_organizer skill."""

import shutil
from pathlib import Path
from typing import Any

EXTENSION_MAP = {
    "Documents": [".pdf", ".docx", ".doc", ".txt", ".xlsx", ".pptx", ".csv"],
    "Images": [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".svg", ".webp"],
    "Archives": [".zip", ".tar", ".gz", ".7z", ".rar"],
    "Code": [".py", ".js", ".ts", ".html", ".css", ".json", ".yaml", ".yml"],
}


def run(args: dict[str, Any]) -> dict[str, Any]:
    folder_str = args.get("folder", "")
    dry_run = args.get("dry_run", True)

    if not folder_str:
        return {"status": "error", "error": "Missing 'folder' argument."}

    p = Path(folder_str)
    if not p.exists() or not p.is_dir():
        return {"status": "error", "error": f"Folder not found: {folder_str}"}

    planned_moves = []
    for item in p.iterdir():
        if item.is_file():
            ext = item.suffix.lower()
            target_category = "Other"
            for cat, exts in EXTENSION_MAP.items():
                if ext in exts:
                    target_category = cat
                    break
            target_dir = p / target_category
            planned_moves.append((item, target_dir / item.name))

    if not planned_moves:
        return {"status": "ok", "output": f"No files found to organize in {p.name}."}

    if dry_run:
        summary_lines = [f"[Dry run] {src.name} -> {dst.parent.name}/{dst.name}" for src, dst in planned_moves[:15]]
        return {
            "status": "ok",
            "output": f"Dry-run planned {len(planned_moves)} file movements:\n" + "\n".join(summary_lines),
            "moved_count": 0,
        }

    # Execute moves
    moved = 0
    for src, dst in planned_moves:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
        moved += 1

    return {
        "status": "ok",
        "output": f"Successfully organized {moved} files in {p.name}.",
        "moved_count": moved,
    }
