"""T.A.R.O. - Trusted-action list.

ARCHITECTURE reference: section 8, 12.
TASKS: TASK-033.

Allows the user to approve a specific action pattern once so it runs without
prompting. Any action can be revoked at any time.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.log.setup import get_logger

logger = get_logger(__name__)


@dataclass
class TrustedAction:
    """An approved action pattern."""

    id: str
    tool_name: str
    pattern: str  # Regex or wildcard matching argument string or path
    created_at: str
    description: str = ""


class TrustedActionStore:
    """Persistent storage for approved action patterns."""

    def __init__(self, storage_path: Path | str = "data/procedural/trusted_actions.json") -> None:
        self.path = Path(storage_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.actions: dict[str, TrustedAction] = {}
        self.load()

    def load(self) -> None:
        """Loads trusted actions from JSON file."""
        if not self.path.exists():
            return
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data: list[dict[str, Any]] = json.load(f)
            self.actions = {item["id"]: TrustedAction(**item) for item in data}
            logger.info("trusted_actions_loaded", count=len(self.actions))
        except Exception as e:
            logger.error("trusted_actions_load_error", error=str(e))

    def save(self) -> None:
        """Saves trusted actions to JSON file."""
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump([asdict(a) for a in self.actions.values()], f, indent=2)
        except Exception as e:
            logger.error("trusted_actions_save_error", error=str(e))

    def is_trusted(self, tool_name: str, argument_str: str) -> bool:
        """Checks if a given tool invocation matches any trusted pattern."""
        import fnmatch

        for action in self.actions.values():
            if action.tool_name == tool_name:
                if fnmatch.fnmatch(argument_str, action.pattern):
                    return True
        return False

    def add(self, tool_name: str, pattern: str, description: str = "") -> str:
        """Adds a pattern to the trusted action list."""
        action_id = f"ta_{tool_name}_{len(self.actions) + 1}"
        action = TrustedAction(
            id=action_id,
            tool_name=tool_name,
            pattern=pattern,
            created_at=datetime.now(timezone.utc).isoformat(),
            description=description,
        )
        self.actions[action_id] = action
        self.save()
        logger.info("trusted_action_added", id=action_id, tool=tool_name, pattern=pattern)
        return action_id

    def revoke(self, action_id: str) -> bool:
        """Revokes a trusted action pattern."""
        if action_id in self.actions:
            del self.actions[action_id]
            self.save()
            logger.info("trusted_action_revoked", id=action_id)
            return True
        return False

    def list_actions(self) -> list[TrustedAction]:
        """Returns all registered trusted actions."""
        return list(self.actions.values())


# Global singleton
_trusted_store: TrustedActionStore | None = None


def get_trusted_store() -> TrustedActionStore:
    """Returns singleton TrustedActionStore."""
    global _trusted_store
    if _trusted_store is None:
        _trusted_store = TrustedActionStore()
    return _trusted_store
