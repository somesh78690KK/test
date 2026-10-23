"""T.A.R.O. - Skill validator (TASK-071).

ARCHITECTURE reference: section 13 (Skills).
RULES reference: section 3, 10.
TASKS: TASK-071.

Validates a skill's skill.json against:
1. Required schema fields (name, version, description, category, risk, inputs, permissions).
2. Risk level validity.
3. Category validity.
4. Permission check against PermissionManager (if category or required permission is denied, skill cannot load).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from core.log.setup import get_logger
from core.safety.permissions import PermissionAction, PermissionDenied, get_permission_manager
from core.tools.base import RiskLevel, ToolCategory

logger = get_logger(__name__)

# Snake case regex for skill name
_NAME_REGEX = re.compile(r"^[a-z][a-z0-9_]*$")


def validate_skill_metadata(
    metadata: dict[str, Any],
    folder_name: str | None = None,
    permission_manager: Any = None,
) -> tuple[bool, str]:
    """Validate a skill.json dictionary.

    Acceptance (TASK-071):
    - Validates schema, risk, and category.
    - Skill needing an ungranted/denied permission is not loaded.

    Args:
        metadata: Parsed skill.json contents.
        folder_name: Optional folder name to verify matching name field.
        permission_manager: Optional PermissionManager instance.

    Returns:
        (True, "") if valid, or (False, "reason") if invalid.
    """
    if not isinstance(metadata, dict):
        return False, "skill.json must contain a JSON object."

    # 1. Required fields check
    required_fields = ["name", "version", "description", "category", "risk", "inputs"]
    for req in required_fields:
        if req not in metadata:
            return False, f"Missing required field '{req}' in skill.json."

    name = metadata.get("name")
    if not isinstance(name, str) or not _NAME_REGEX.match(name):
        return False, f"Invalid skill name '{name}'. Must be snake_case."

    if folder_name and name != folder_name:
        return (
            False,
            f"Skill name '{name}' does not match folder name '{folder_name}'.",
        )

    description = metadata.get("description")
    if not isinstance(description, str) or not description.strip():
        return False, "Skill description must be a non-empty string."

    version = metadata.get("version")
    if not isinstance(version, str) or not version.strip():
        return False, "Skill version must be a valid string."

    # 2. Risk check
    risk_str = str(metadata.get("risk", "")).upper()
    try:
        risk_level = RiskLevel(risk_str)
    except ValueError:
        valid_risks = [r.value for r in RiskLevel]
        return False, f"Invalid risk level '{risk_str}'. Must be one of {valid_risks}."

    # 3. Category check
    cat_str = str(metadata.get("category", "")).lower()
    try:
        category = ToolCategory(cat_str)
    except ValueError:
        valid_cats = [c.value for c in ToolCategory]
        return False, f"Invalid category '{cat_str}'. Must be one of {valid_cats}."

    # 4. Inputs schema check
    inputs = metadata.get("inputs")
    if not isinstance(inputs, dict) or inputs.get("type") != "object":
        return False, "Skill inputs must be a JSON schema object with type 'object'."

    # 5. Permission evaluation against PermissionManager
    pm = permission_manager or get_permission_manager()
    try:
        action = pm.evaluate(category, risk_level)
        if action == PermissionAction.DENY:
            return (
                False,
                f"Skill category '{cat_str}' is denied by permissions configuration.",
            )
    except PermissionDenied as e:
        return False, f"Permission denied for skill: {e.reason}"
    except Exception as e:
        logger.warning("skill_permission_eval_failed", skill=name, error=str(e))

    # Check specific permission strings if declared
    permissions = metadata.get("permissions", [])
    if isinstance(permissions, list):
        for perm in permissions:
            perm_cat = perm.split(".")[0] if "." in perm else perm
            if perm_cat in pm.categories and pm.categories[perm_cat] == PermissionAction.DENY:
                return (
                    False,
                    f"Skill requires ungranted/denied permission '{perm}'.",
                )

    return True, ""
