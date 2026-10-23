"""T.A.R.O. - Skill Forge registrar (TASK-118).

ARCHITECTURE reference: section 18 (Self-Extension & Forge).
RULES reference: section 3, 4, 10.
TASKS: TASK-117, TASK-118.

Manages the lifecycle of forge-generated skills:
1. Two-step approval: spec approval + code review approval.
2. Hash-based manifest for tamper detection (modified file = disabled).
3. Trial state: newly forged skills prompt for first 3 runs.
4. Hot-load into the skill loader after registration.

Acceptance (TASK-118): Modified skill file is disabled on next load;
trial asks first 3 runs.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

from core.log.setup import get_logger

logger = get_logger(__name__)

MANIFEST_FILE = Path("data/skill_manifest.json")


class SkillManifest:
    """Tracks SHA-256 hashes and metadata for every registered forged skill."""

    def __init__(self, manifest_path: Path | str | None = None) -> None:
        self._path = Path(manifest_path) if manifest_path else MANIFEST_FILE
        self._entries: dict[str, dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        if self._path.exists():
            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    self._entries = json.load(f)
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("manifest_load_failed", error=str(e))
                self._entries = {}

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(self._entries, f, indent=2)

    @staticmethod
    def _hash_file(file_path: Path) -> str:
        """Compute SHA-256 hash of a file."""
        h = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()

    def register(self, skill_name: str, skill_dir: Path | str) -> dict[str, Any]:
        """Register a forged skill with its file hashes."""
        skill_path = Path(skill_dir)
        files_hashes: dict[str, str] = {}

        for fpath in skill_path.iterdir():
            if fpath.is_file():
                files_hashes[fpath.name] = self._hash_file(fpath)

        entry = {
            "name": skill_name,
            "path": str(skill_path),
            "state": "trial",  # trial | active | disabled
            "run_count": 0,
            "trial_limit": 3,
            "registered_at": time.time(),
            "file_hashes": files_hashes,
        }

        self._entries[skill_name] = entry
        self._save()
        logger.info("skill_registered", name=skill_name, state="trial")
        return entry

    def verify_integrity(self, skill_name: str) -> tuple[bool, list[str]]:
        """Verify all files match their registered hashes."""
        entry = self._entries.get(skill_name)
        if not entry:
            return False, [f"Skill '{skill_name}' not in manifest."]

        skill_path = Path(entry["path"])
        tampered: list[str] = []

        for filename, expected_hash in entry.get("file_hashes", {}).items():
            fpath = skill_path / filename
            if not fpath.exists():
                tampered.append(f"Missing file: {filename}")
                continue
            actual_hash = self._hash_file(fpath)
            if actual_hash != expected_hash:
                tampered.append(f"Modified file: {filename}")

        if tampered:
            # Automatically disable tampered skill
            self._entries[skill_name]["state"] = "disabled"
            self._save()
            logger.warning("skill_tampered_disabled", name=skill_name, issues=tampered)
            return False, tampered

        return True, []

    def record_run(self, skill_name: str) -> str:
        """Record a skill execution. Returns new state."""
        entry = self._entries.get(skill_name)
        if not entry:
            return "unknown"

        entry["run_count"] = entry.get("run_count", 0) + 1

        # Graduate from trial to active after trial_limit runs
        if entry["state"] == "trial" and entry["run_count"] >= entry.get("trial_limit", 3):
            entry["state"] = "active"
            logger.info("skill_graduated", name=skill_name, runs=entry["run_count"])

        self._save()
        return entry["state"]

    def is_trial(self, skill_name: str) -> bool:
        """Check if a skill is still in trial state."""
        entry = self._entries.get(skill_name)
        return entry is not None and entry.get("state") == "trial"

    def get_state(self, skill_name: str) -> str:
        """Get the current state of a skill."""
        entry = self._entries.get(skill_name)
        return entry.get("state", "unknown") if entry else "unknown"

    def disable(self, skill_name: str) -> None:
        """Disable a skill."""
        if skill_name in self._entries:
            self._entries[skill_name]["state"] = "disabled"
            self._save()
            logger.info("skill_disabled", name=skill_name)

    def enable(self, skill_name: str) -> None:
        """Re-enable a disabled skill after rehash."""
        if skill_name in self._entries:
            # Re-hash all files
            entry = self._entries[skill_name]
            skill_path = Path(entry["path"])
            files_hashes: dict[str, str] = {}
            for fpath in skill_path.iterdir():
                if fpath.is_file():
                    files_hashes[fpath.name] = self._hash_file(fpath)
            entry["file_hashes"] = files_hashes
            entry["state"] = "active"
            self._save()
            logger.info("skill_re_enabled", name=skill_name)

    def list_skills(self) -> list[dict[str, Any]]:
        """Return all registered skills and their states."""
        return [
            {
                "name": name,
                "state": entry.get("state", "unknown"),
                "run_count": entry.get("run_count", 0),
                "path": entry.get("path", ""),
            }
            for name, entry in self._entries.items()
        ]


class ForgeApprovalManager:
    """Two-step approval flow for forge-generated skills (TASK-117).

    Step 1: Spec approval (user reviews skill.json before code generation).
    Step 2: Code review approval (user reviews generated code + test results).

    Code never registers without both approvals in 'ask' mode.
    """

    def __init__(self, manifest: SkillManifest | None = None) -> None:
        self.manifest = manifest or SkillManifest()
        self._pending: dict[str, dict[str, Any]] = {}

    def submit_spec_for_approval(
        self, skill_name: str, spec: dict[str, Any]
    ) -> dict[str, Any]:
        """Submit a skill spec for step-1 approval."""
        self._pending[skill_name] = {
            "spec": spec,
            "spec_approved": False,
            "code_approved": False,
            "code": None,
            "test_report": None,
        }
        return {
            "type": "forge_spec_review",
            "skill_name": skill_name,
            "spec": spec,
            "risk": spec.get("risk", "UNKNOWN"),
            "permissions": spec.get("permissions", []),
        }

    def approve_spec(self, skill_name: str) -> bool:
        """Mark step-1 (spec) as approved."""
        if skill_name in self._pending:
            self._pending[skill_name]["spec_approved"] = True
            logger.info("forge_spec_approved", name=skill_name)
            return True
        return False

    def deny_spec(self, skill_name: str) -> bool:
        """Deny spec - leaves no files."""
        if skill_name in self._pending:
            del self._pending[skill_name]
            logger.info("forge_spec_denied", name=skill_name)
            return True
        return False

    def submit_code_for_review(
        self,
        skill_name: str,
        code: str,
        test_report: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Submit generated code + test results for step-2 approval."""
        pending = self._pending.get(skill_name)
        if not pending or not pending["spec_approved"]:
            return None

        pending["code"] = code
        pending["test_report"] = test_report

        return {
            "type": "forge_code_review",
            "skill_name": skill_name,
            "code_preview": code[:500] + ("..." if len(code) > 500 else ""),
            "test_report": test_report,
        }

    def approve_code(self, skill_name: str) -> bool:
        """Mark step-2 (code) as approved. Now eligible for registration."""
        pending = self._pending.get(skill_name)
        if pending and pending["spec_approved"]:
            pending["code_approved"] = True
            logger.info("forge_code_approved", name=skill_name)
            return True
        return False

    def deny_code(self, skill_name: str) -> bool:
        """Deny code review - cleans up pending state."""
        if skill_name in self._pending:
            del self._pending[skill_name]
            logger.info("forge_code_denied", name=skill_name)
            return True
        return False

    def is_fully_approved(self, skill_name: str) -> bool:
        """Check if a skill has passed both approval steps."""
        pending = self._pending.get(skill_name)
        if not pending:
            return False
        return pending["spec_approved"] and pending["code_approved"]

    def finalize_registration(self, skill_name: str, skill_dir: Path | str) -> dict[str, Any] | None:
        """Register the skill in the manifest after full approval."""
        if not self.is_fully_approved(skill_name):
            logger.warning("forge_registration_blocked", name=skill_name, reason="Not fully approved")
            return None

        entry = self.manifest.register(skill_name, skill_dir)

        # Clean up pending
        if skill_name in self._pending:
            del self._pending[skill_name]

        return entry
