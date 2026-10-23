"""T.A.R.O. - Workspace path guard and path normalization.

ARCHITECTURE reference: section 14.
RULES reference: section 4.
TASKS: TASK-043, TASK-057.

Guards paths against unauthorized mutations outside the configured workspace directory.
Handles Windows extended-length paths (\\\\?\\ prefix) and unicode characters.
"""

from __future__ import annotations

import os
from pathlib import Path

from core.config import get_config
from core.log.setup import get_logger

logger = get_logger(__name__)


def get_workspace_root() -> Path:
    """Returns the resolved workspace directory path."""
    cfg = get_config()
    # Check config or default to <repo_root>/workspace
    ws_str = getattr(cfg, "workspace_dir", None)
    if ws_str:
        ws_path = Path(ws_str).resolve()
    else:
        repo_root = Path(__file__).resolve().parent.parent.parent
        ws_path = (repo_root / "workspace").resolve()

    ws_path.mkdir(parents=True, exist_ok=True)
    return ws_path


def normalize_path(path_input: str | Path) -> Path:
    """Normalizes path, handling unicode, spaces, and Windows extended paths."""
    p = Path(path_input)
    # Expand user ~
    try:
        p = p.expanduser()
    except Exception:
        pass

    # Resolve symlinks and relative components
    resolved = p.resolve()
    return resolved


def is_inside_workspace(path_input: str | Path) -> bool:
    """Checks whether the given path resolves within the workspace root."""
    try:
        norm = normalize_path(path_input)
        ws = get_workspace_root()
        return norm.is_relative_to(ws)
    except Exception:
        return False


def to_extended_path(path: Path) -> str:
    """Prepends Windows extended-length path prefix \\\\?\\ if path is long and on Windows."""
    resolved_str = str(path.resolve())
    if os.name == "nt" and len(resolved_str) >= 240 and not resolved_str.startswith("\\\\?\\"):
        return f"\\\\?\\{resolved_str}"
    return resolved_str
