"""T.A.R.O. - Permission map and evaluation.

ARCHITECTURE reference: section 8.
RULES reference: section 4.
TASKS: TASK-031.

Evaluates permissions per category and risk level using config/permissions.json.
Cloud category is denied by default unless explicitly allowed.
"""

from __future__ import annotations

import json
from enum import StrEnum
from pathlib import Path
from typing import Any

from core.log.setup import get_logger
from core.tools.base import RiskLevel, ToolCategory

logger = get_logger(__name__)


class SafetyBlock(Exception):
    """Base exception for safety and permission blocks."""


class PermissionDenied(SafetyBlock):
    """Raised when an action is blocked by the permission map."""

    def __init__(self, category: str, reason: str = "") -> None:
        self.category = category
        self.reason = reason
        super().__init__(f"Permission denied for category '{category}': {reason}")


class PermissionAction(StrEnum):
    ALLOW = "allow"
    ASK = "ask"
    ASK_TYPED = "ask_typed"
    DENY = "deny"


class PermissionManager:
    """Loads and evaluates permission rules for tool execution."""

    def __init__(self, permissions_path: Path | str | None = None) -> None:
        if permissions_path is None:
            self.path = Path("config/permissions.json")
        else:
            self.path = Path(permissions_path)
        self.categories: dict[str, PermissionAction] = {}
        self.risk_defaults: dict[str, PermissionAction] = {
            "SAFE": PermissionAction.ALLOW,
            "LOW": PermissionAction.ALLOW,
            "MEDIUM": PermissionAction.ASK,
            "HIGH": PermissionAction.ASK_TYPED,
            "CRITICAL": PermissionAction.ASK_TYPED,
        }
        self.reload()

    def reload(self) -> None:
        """Reloads permissions from disk."""
        if not self.path.exists():
            logger.warning("permissions_file_not_found", path=str(self.path))
            return

        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data: dict[str, Any] = json.load(f)

            raw_categories = data.get("categories", {})
            for cat, act in raw_categories.items():
                try:
                    self.categories[cat] = PermissionAction(act)
                except ValueError:
                    logger.error("invalid_permission_action", category=cat, action=act)

            raw_risks = data.get("risk_defaults", {})
            for rsk, act in raw_risks.items():
                try:
                    self.risk_defaults[rsk] = PermissionAction(act)
                except ValueError:
                    logger.error("invalid_risk_action", risk=rsk, action=act)

            logger.info("permissions_loaded", count=len(self.categories))
        except Exception as e:
            logger.error("permissions_load_failed", error=str(e))
            raise

    def evaluate(
        self,
        category: ToolCategory | str,
        risk: RiskLevel,
    ) -> PermissionAction:
        """Determines whether a tool execution is allowed, needs confirmation, or denied.

        Rule:
        1. If category is DENY in permissions.json -> DENY immediately.
        2. If category is ASK -> at least ASK.
        3. Risk level escalates requirement (e.g. HIGH/CRITICAL always requires ASK_TYPED).
        4. Whichever rule is more restrictive wins.
        """
        cat_str = category.value if isinstance(category, ToolCategory) else str(category)
        cat_action = self.categories.get(cat_str, PermissionAction.ASK)

        if cat_action == PermissionAction.DENY:
            raise PermissionDenied(
                category=cat_str,
                reason=f"Category '{cat_str}' is configured as 'deny' in {self.path.name}.",
            )

        # Baseline from risk level
        risk_action = self.risk_defaults.get(risk.name, PermissionAction.ASK_TYPED)

        # Priority: DENY > ASK_TYPED > ASK > ALLOW
        priority = {
            PermissionAction.ALLOW: 1,
            PermissionAction.ASK: 2,
            PermissionAction.ASK_TYPED: 3,
            PermissionAction.DENY: 4,
        }

        if priority[cat_action] >= priority[risk_action]:
            return cat_action
        return risk_action


# Singleton instance
_manager: PermissionManager | None = None


def get_permission_manager(path: Path | str | None = None) -> PermissionManager:
    """Returns the singleton PermissionManager."""
    global _manager
    if _manager is None or path is not None:
        _manager = PermissionManager(path)
    return _manager
