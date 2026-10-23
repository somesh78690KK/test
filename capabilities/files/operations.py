"""T.A.R.O. - File operations capability.

ARCHITECTURE reference: section 14.
RULES reference: section 3, 4, 10.
TASKS: TASK-043, TASK-057, TASK-140.

Tools for reading, writing, copying, moving, renaming, deleting, listing,
and searching files. Robust against paths with spaces, non-ASCII/Unicode
characters (e.g. 'Test Folder ñ 日本'), and Windows long paths.
"""

from __future__ import annotations

import datetime
import fnmatch
import json
import os
import shutil
from pathlib import Path
from typing import Any

from capabilities.files.workspace import (
    is_inside_workspace,
    normalize_path,
    to_extended_path,
)
from core.log.setup import get_logger
from core.safety.immutable import is_path_immutable
from core.tools.base import BaseTool, RiskLevel, ToolCategory, ToolResult

logger = get_logger(__name__)

# Max read size (512 KB) to prevent context flooding
MAX_READ_BYTES = 512 * 1024


def _get_recovery_dir() -> Path:
    repo_root = Path(__file__).resolve().parent.parent.parent
    rec = repo_root / "data" / "recovery"
    rec.mkdir(parents=True, exist_ok=True)
    return rec


class _FileBaseTool(BaseTool):
    async def run(self, args: dict) -> ToolResult:
        return await self.execute(**args)


class FileReadTool(_FileBaseTool):
    """Reads content of a file."""

    name = "file.read"
    description = "Read text content of a file."
    category = ToolCategory.FILES
    risk = RiskLevel.SAFE
    timeout_s = 10
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path to the file to read."}
        },
        "required": ["path"],
    }

    async def execute(self, **kwargs: Any) -> ToolResult:
        path_str = kwargs.get("path")
        if not path_str:
            return ToolResult(status="error", output="", error="Missing 'path' argument.")

        try:
            norm = normalize_path(path_str)
            ext_path = to_extended_path(norm)
            if not os.path.exists(ext_path):
                return ToolResult(status="error", output="", error=f"File not found: {path_str}")

            if os.path.isdir(ext_path):
                return ToolResult(status="error", output="", error=f"Path is a directory, not a file: {path_str}")

            size = os.path.getsize(ext_path)
            if size > MAX_READ_BYTES:
                with open(ext_path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read(MAX_READ_BYTES)
                return ToolResult(
                    status="ok",
                    output=f"{content}\n\n[TRUNCATED: File size {size} bytes exceeds limit of {MAX_READ_BYTES} bytes]",
                )

            with open(ext_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()

            return ToolResult(status="ok", output=content)
        except Exception as e:
            logger.error("file_read_error", path=path_str, error=str(e))
            return ToolResult(status="error", output="", error=f"Failed to read file: {e}")


class FileWriteTool(_FileBaseTool):
    """Writes text content to a file."""

    name = "file.write"
    description = "Write text content to a file."
    category = ToolCategory.FILES
    risk = RiskLevel.MEDIUM
    timeout_s = 15
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Target file path."},
            "content": {"type": "string", "description": "Content to write."},
            "append": {"type": "boolean", "description": "Append instead of overwrite."},
        },
        "required": ["path", "content"],
    }

    async def execute(self, **kwargs: Any) -> ToolResult:
        path_str = kwargs.get("path")
        content = kwargs.get("content", "")
        append = kwargs.get("append", False)
        dry_run = kwargs.get("dry_run", False)

        if not path_str:
            return ToolResult(status="error", output="", error="Missing 'path' argument.")

        if is_path_immutable(path_str):
            return ToolResult(
                status="error",
                output="",
                error=f"Permission Denied: Path '{path_str}' is protected by immutable system policy.",
            )

        if dry_run:
            return ToolResult(
                status="ok",
                output=f"[DRY RUN] Planned write of {len(content)} characters to '{path_str}'. No changes made.",
            )

        try:
            norm = normalize_path(path_str)
            ext_path = to_extended_path(norm)
            parent = norm.parent
            parent_ext = to_extended_path(parent)
            os.makedirs(parent_ext, exist_ok=True)

            mode = "a" if append else "w"
            with open(ext_path, mode, encoding="utf-8") as f:
                f.write(content)

            return ToolResult(
                status="ok",
                output=f"Successfully {'appended to' if append else 'wrote'} {len(content)} characters to {norm}",
            )
        except Exception as e:
            logger.error("file_write_error", path=path_str, error=str(e))
            return ToolResult(status="error", output="", error=f"Failed to write file: {e}")


class FileCopyTool(_FileBaseTool):
    """Copies a file or folder from source to destination."""

    name = "file.copy"
    description = "Copy a file or directory to a new location."
    category = ToolCategory.FILES
    risk = RiskLevel.LOW
    timeout_s = 30
    parameters = {
        "type": "object",
        "properties": {
            "source": {"type": "string", "description": "Source path."},
            "destination": {"type": "string", "description": "Destination path."},
        },
        "required": ["source", "destination"],
    }

    async def execute(self, **kwargs: Any) -> ToolResult:
        src_str = kwargs.get("source")
        dst_str = kwargs.get("destination")
        if not src_str or not dst_str:
            return ToolResult(status="error", output="", error="Both 'source' and 'destination' are required.")

        try:
            src = normalize_path(src_str)
            dst = normalize_path(dst_str)
            src_ext = to_extended_path(src)
            dst_ext = to_extended_path(dst)

            if not os.path.exists(src_ext):
                return ToolResult(status="error", output="", error=f"Source does not exist: {src_str}")

            if os.path.isdir(src_ext):
                shutil.copytree(src_ext, dst_ext, dirs_exist_ok=True)
            else:
                os.makedirs(to_extended_path(dst.parent), exist_ok=True)
                shutil.copy2(src_ext, dst_ext)

            return ToolResult(status="ok", output=f"Copied '{src}' to '{dst}' successfully.")
        except Exception as e:
            logger.error("file_copy_error", src=src_str, dst=dst_str, error=str(e))
            return ToolResult(status="error", output="", error=f"Failed to copy: {e}")


class FileMoveTool(_FileBaseTool):
    """Moves a file or folder."""

    name = "file.move"
    description = "Move a file or directory to a new location."
    category = ToolCategory.FILES
    risk = RiskLevel.MEDIUM
    timeout_s = 20
    parameters = {
        "type": "object",
        "properties": {
            "source": {"type": "string", "description": "Source path."},
            "destination": {"type": "string", "description": "Destination path."},
        },
        "required": ["source", "destination"],
    }

    async def execute(self, **kwargs: Any) -> ToolResult:
        src_str = kwargs.get("source")
        dst_str = kwargs.get("destination")
        if not src_str or not dst_str:
            return ToolResult(status="error", output="", error="Both 'source' and 'destination' are required.")

        try:
            src = normalize_path(src_str)
            dst = normalize_path(dst_str)
            src_ext = to_extended_path(src)
            dst_ext = to_extended_path(dst)

            if not os.path.exists(src_ext):
                return ToolResult(status="error", output="", error=f"Source does not exist: {src_str}")

            os.makedirs(to_extended_path(dst.parent), exist_ok=True)
            shutil.move(src_ext, dst_ext)
            return ToolResult(status="ok", output=f"Moved '{src}' to '{dst}' successfully.")
        except Exception as e:
            logger.error("file_move_error", src=src_str, dst=dst_str, error=str(e))
            return ToolResult(status="error", output="", error=f"Failed to move: {e}")


class FileRenameTool(_FileBaseTool):
    """Renames a file or folder."""

    name = "file.rename"
    description = "Rename a file or directory."
    category = ToolCategory.FILES
    risk = RiskLevel.MEDIUM
    timeout_s = 15
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path to file or folder."},
            "new_name": {"type": "string", "description": "New file or folder name (not full path)."},
        },
        "required": ["path", "new_name"],
    }

    async def execute(self, **kwargs: Any) -> ToolResult:
        path_str = kwargs.get("path")
        new_name = kwargs.get("new_name")
        dry_run = kwargs.get("dry_run", False)
        if not path_str or not new_name:
            return ToolResult(status="error", output="", error="Both 'path' and 'new_name' are required.")

        if is_path_immutable(path_str):
            return ToolResult(
                status="error",
                output="",
                error=f"Permission Denied: Path '{path_str}' is protected by immutable system policy.",
            )

        if dry_run:
            return ToolResult(
                status="ok",
                output=f"[DRY RUN] Planned rename of '{path_str}' to '{new_name}'. No changes made.",
            )

        try:
            target = normalize_path(path_str)
            dest = target.parent / new_name
            target_ext = to_extended_path(target)
            dest_ext = to_extended_path(dest)

            if not os.path.exists(target_ext):
                return ToolResult(status="error", output="", error=f"Target path does not exist: {path_str}")

            os.rename(target_ext, dest_ext)
            return ToolResult(status="ok", output=f"Renamed '{target.name}' to '{new_name}'.")
        except Exception as e:
            logger.error("file_rename_error", path=path_str, new_name=new_name, error=str(e))
            return ToolResult(status="error", output="", error=f"Failed to rename: {e}")


class FileDeleteTool(_FileBaseTool):
    """Deletes a file or directory, moving to recovery folder first."""

    name = "file.delete"
    description = "Delete a file or directory (saved to recovery)."
    category = ToolCategory.FILES
    risk = RiskLevel.HIGH
    timeout_s = 20
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path to delete."},
            "dry_run": {"type": "boolean", "description": "Simulate deletion without making changes."},
        },
        "required": ["path"],
    }

    async def execute(self, **kwargs: Any) -> ToolResult:
        path_str = kwargs.get("path")
        dry_run = kwargs.get("dry_run", False)
        if not path_str:
            return ToolResult(status="error", output="", error="Missing 'path' argument.")

        if is_path_immutable(path_str):
            return ToolResult(
                status="error",
                output="",
                error=f"Permission Denied: Path '{path_str}' is protected by immutable system policy.",
            )

        if dry_run:
            return ToolResult(
                status="ok",
                output=f"[DRY RUN] Planned delete of '{path_str}'. No changes made.",
            )

        try:
            target = normalize_path(path_str)
            target_ext = to_extended_path(target)

            if not os.path.exists(target_ext):
                return ToolResult(status="error", output="", error=f"Target does not exist: {path_str}")

            # Backup to recovery folder before deletion
            rec_dir = _get_recovery_dir()
            ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d_%H%M%S")
            backup_name = f"{ts}_{target.name}"
            backup_dest = rec_dir / backup_name

            is_dir = os.path.isdir(target_ext)
            if is_dir:
                shutil.copytree(target_ext, to_extended_path(backup_dest))
                shutil.rmtree(target_ext)
            else:
                shutil.copy2(target_ext, to_extended_path(backup_dest))
                os.remove(target_ext)

            # Record in recovery index for undo (TASK-140)
            meta_file = rec_dir / "recovery_index.json"
            index = {}
            if meta_file.exists():
                try:
                    with open(meta_file, "r", encoding="utf-8") as f:
                        index = json.load(f)
                except Exception:
                    index = {}
            index[backup_name] = {
                "original_path": str(target),
                "timestamp": ts,
                "is_dir": is_dir,
            }
            with open(meta_file, "w", encoding="utf-8") as f:
                json.dump(index, f, indent=2)

            inside_ws = is_inside_workspace(target)
            msg = f"Deleted '{target}' (backup saved to recovery: '{backup_dest.name}'). Inside workspace: {inside_ws}."
            return ToolResult(status="ok", output=msg)
        except Exception as e:
            logger.error("file_delete_error", path=path_str, error=str(e))
            return ToolResult(status="error", output="", error=f"Failed to delete: {e}")


class FileUndoTool(_FileBaseTool):
    """Restores the most recently deleted file from recovery folder (TASK-140)."""

    name = "file.undo"
    description = "Restore a previously deleted file from the recovery folder."
    category = ToolCategory.FILES
    risk = RiskLevel.MEDIUM
    timeout_s = 15
    parameters = {
        "type": "object",
        "properties": {
            "target": {"type": "string", "description": "Optional specific file name to restore."},
        },
    }

    async def execute(self, **kwargs: Any) -> ToolResult:
        rec_dir = _get_recovery_dir()
        meta_file = rec_dir / "recovery_index.json"
        index: dict[str, Any] = {}
        if meta_file.exists():
            try:
                with open(meta_file, "r", encoding="utf-8") as f:
                    index = json.load(f)
            except Exception:
                index = {}

        target_arg = kwargs.get("target")

        if not index:
            # Fallback to inspecting directory directly
            items = sorted(rec_dir.glob("*"), key=lambda p: p.stat().st_mtime, reverse=True)
            items = [i for i in items if i.name != "recovery_index.json"]
            if not items:
                return ToolResult(status="ok", output="Recovery folder is empty. Nothing to undo.")
            target_backup = items[0]
            # Strip timestamp prefix
            parts = target_backup.name.split("_", 2)
            orig_name = parts[-1] if len(parts) >= 3 else target_backup.name
            restore_dest = Path("workspace") / orig_name
            backup_key = target_backup.name
        else:
            if target_arg:
                matched_key = None
                for k, v in index.items():
                    if target_arg in k or target_arg in v.get("original_path", ""):
                        matched_key = k
                        break
                if not matched_key:
                    return ToolResult(status="error", output="", error=f"File matching '{target_arg}' not found in recovery.")
                backup_key = matched_key
            else:
                backup_key = list(index.keys())[-1]

            entry = index.pop(backup_key)
            target_backup = rec_dir / backup_key
            restore_dest = Path(entry.get("original_path", Path("workspace") / target_backup.name))

        if not target_backup.exists():
            return ToolResult(status="error", output="", error=f"Backup '{target_backup.name}' not found on disk.")

        try:
            restore_dest.parent.mkdir(parents=True, exist_ok=True)
            if target_backup.is_dir():
                shutil.copytree(str(target_backup), str(restore_dest), dirs_exist_ok=True)
                shutil.rmtree(str(target_backup))
            else:
                shutil.copy2(str(target_backup), str(restore_dest))
                target_backup.unlink()

            if meta_file.exists():
                with open(meta_file, "w", encoding="utf-8") as f:
                    json.dump(index, f, indent=2)

            return ToolResult(status="ok", output=f"Successfully restored '{restore_dest.name}' to '{restore_dest}'.")
        except Exception as e:
            logger.error("file_undo_error", error=str(e))
            return ToolResult(status="error", output="", error=f"Failed to restore file: {e}")


class FileListTool(_FileBaseTool):
    """Lists files and folders inside a directory."""

    name = "file.list"
    description = "List files and directories at a path."
    category = ToolCategory.FILES
    risk = RiskLevel.SAFE
    timeout_s = 10
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Directory path."}
        },
        "required": ["path"],
    }

    async def execute(self, **kwargs: Any) -> ToolResult:
        path_str = kwargs.get("path", ".")
        try:
            norm = normalize_path(path_str)
            ext_path = to_extended_path(norm)
            if not os.path.exists(ext_path):
                return ToolResult(status="error", output="", error=f"Path does not exist: {path_str}")

            if not os.path.isdir(ext_path):
                return ToolResult(status="error", output="", error=f"Path is not a directory: {path_str}")

            entries = []
            for item in os.listdir(ext_path):
                item_full = os.path.join(ext_path, item)
                kind = "DIR " if os.path.isdir(item_full) else "FILE"
                entries.append(f"[{kind}] {item}")

            output = f"Contents of {norm} ({len(entries)} items):\n" + "\n".join(sorted(entries))
            return ToolResult(status="ok", output=output)
        except Exception as e:
            return ToolResult(status="error", output="", error=f"Failed to list directory: {e}")


class FileSearchTool(_FileBaseTool):
    """Searches for files matching a pattern."""

    name = "file.search"
    description = "Search for files matching a pattern within a directory."
    category = ToolCategory.FILES
    risk = RiskLevel.SAFE
    timeout_s = 20
    parameters = {
        "type": "object",
        "properties": {
            "directory": {"type": "string", "description": "Directory to search within."},
            "pattern": {"type": "string", "description": "Glob pattern (e.g., '*.py' or '*report*')."},
            "max_results": {"type": "integer", "description": "Maximum number of results to return."},
        },
        "required": ["directory", "pattern"],
    }

    async def execute(self, **kwargs: Any) -> ToolResult:
        dir_str = kwargs.get("directory", ".")
        pattern = kwargs.get("pattern", "*")
        max_results = kwargs.get("max_results", 50)

        try:
            base_dir = normalize_path(dir_str)
            ext_base = to_extended_path(base_dir)
            if not os.path.isdir(ext_base):
                return ToolResult(status="error", output="", error=f"Search directory not found: {dir_str}")

            matches: list[str] = []
            for root, _, files in os.walk(ext_base):
                for f in files:
                    if fnmatch.fnmatch(f, pattern):
                        full_p = os.path.join(root, f)
                        matches.append(full_p)
                        if len(matches) >= max_results:
                            break
                if len(matches) >= max_results:
                    break

            if not matches:
                return ToolResult(status="ok", output=f"No files matching '{pattern}' in '{base_dir}'.")

            res_lines = [f"Found {len(matches)} matches for '{pattern}' in '{base_dir}':"]
            res_lines.extend(f"- {m}" for m in matches)
            return ToolResult(status="ok", output="\n".join(res_lines))
        except Exception as e:
            return ToolResult(status="error", output="", error=f"Search failed: {e}")


# List of all file tools
FILE_TOOLS: list[BaseTool] = [
    FileReadTool(),
    FileWriteTool(),
    FileCopyTool(),
    FileMoveTool(),
    FileRenameTool(),
    FileDeleteTool(),
    FileListTool(),
    FileSearchTool(),
    FileUndoTool(),
]
