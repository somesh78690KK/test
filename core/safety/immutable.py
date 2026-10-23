"""T.A.R.O. - Immutable Path & Core Integrity Enforcement (TASK-115, TASK-125).

ARCHITECTURE reference: section 8, section 18.
RULES reference: section 4 (Safety), section 10.
TASKS: TASK-115, TASK-125.

Guarantees system immutability:
1. SHA-256 manifest of immutable core files (core/, config/permissions.json).
2. Startup verification: any modified or tampered file halts execution with an alert.
3. Path boundary guard: blocks write/delete operations directed at immutable directories.
4. OS-level permission helper: scripts/protect_install.bat integration.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from core.log.setup import get_logger

logger = get_logger(__name__)

CORE_MANIFEST_PATH = Path("data/core_manifest.json")

IMMUTABLE_ROOTS = [
    Path("core"),
    Path("config/permissions.json"),
    Path("config/config.yaml"),
]


class ImmutablePathViolation(PermissionError):
    """Raised when an action attempts to write to an immutable system path."""


def is_path_immutable(target_path: Path | str) -> bool:
    """Return True if target_path falls inside an immutable system path."""
    try:
        resolved = Path(target_path).resolve()
    except Exception:
        resolved = Path(target_path)

    for root in IMMUTABLE_ROOTS:
        try:
            root_res = root.resolve()
            if resolved == root_res or root_res in resolved.parents:
                return True
        except Exception:
            continue

    path_str = str(target_path).lower().replace("\\", "/")
    if path_str.startswith("core/") or "/core/" in path_str:
        return True
    if "config/permissions.json" in path_str:
        return True
    if "config/config.yaml" in path_str:
        return True

    return False


def enforce_immutable_path(target_path: Path | str) -> None:
    """Raise ImmutablePathViolation if target_path is immutable."""
    if is_path_immutable(target_path):
        msg = f"Path '{target_path}' is protected by immutable system policy and cannot be modified."
        logger.error("immutable_path_violation_blocked", target=str(target_path))
        raise ImmutablePathViolation(msg)


def compute_file_hash(file_path: Path) -> str:
    """Compute SHA-256 hash of a single file."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def generate_core_manifest(manifest_path: Path | str | None = None) -> dict[str, str]:
    """Generate SHA-256 hashes for all immutable core files and save to disk."""
    out_path = Path(manifest_path) if manifest_path else CORE_MANIFEST_PATH
    out_path.parent.mkdir(parents=True, exist_ok=True)

    manifest: dict[str, str] = {}

    # Hash core/ files
    core_dir = Path("core")
    if core_dir.exists():
        for py_file in sorted(core_dir.rglob("*.py")):
            rel = str(py_file.as_posix())
            manifest[rel] = compute_file_hash(py_file)

    # Hash protected config files
    for cfg_file in [Path("config/permissions.json"), Path("config/config.yaml")]:
        if cfg_file.exists():
            rel = str(cfg_file.as_posix())
            manifest[rel] = compute_file_hash(cfg_file)

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    logger.info("core_manifest_generated", files_count=len(manifest), path=str(out_path))
    return manifest


def verify_core_integrity(manifest_path: Path | str | None = None) -> tuple[bool, list[str]]:
    """Verify core file hashes against the stored manifest.

    Acceptance (TASK-125): Editing a protected file makes startup refuse to run
    and name the file.
    """
    mpath = Path(manifest_path) if manifest_path else CORE_MANIFEST_PATH
    if not mpath.exists():
        # First time or fresh install — generate baseline manifest
        generate_core_manifest(mpath)
        return True, []

    try:
        with open(mpath, "r", encoding="utf-8") as f:
            manifest: dict[str, str] = json.load(f)
    except Exception as e:
        logger.error("core_manifest_corrupted", error=str(e))
        return False, ["MANIFEST_FILE_CORRUPTED"]

    modified_or_missing: list[str] = []

    for rel_path, expected_hash in manifest.items():
        file_path = Path(rel_path)
        if not file_path.exists():
            modified_or_missing.append(f"{rel_path} (missing)")
            continue

        try:
            current_hash = compute_file_hash(file_path)
            if current_hash != expected_hash:
                modified_or_missing.append(f"{rel_path} (tampered/modified)")
        except Exception as e:
            modified_or_missing.append(f"{rel_path} (error: {e})")

    if modified_or_missing:
        logger.critical(
            "core_integrity_check_failed",
            tampered_files=modified_or_missing,
        )
        return False, modified_or_missing

    return True, []
