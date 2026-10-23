"""T.A.R.O. - Skill Forge spec writer (TASK-112).

ARCHITECTURE reference: section 18.
RULES reference: section 3, 10.
TASKS: TASK-112.

Drafts `skill.json` specification from user prompt:
- Determines name, description, risk level, category, permissions.
- Derives input schema.
- Selects base template (file, web, excel, text, api).
- If denied during approval, leaves no trace or lingering files.
"""

from __future__ import annotations

import re
from typing import Any

from core.log.setup import get_logger
from core.tools.base import RiskLevel, ToolCategory

logger = get_logger(__name__)


def draft_skill_spec(
    user_request: str,
    skill_name: str | None = None,
    category: str | None = None,
    risk: str | None = None,
) -> dict[str, Any]:
    """Draft a valid skill.json specification from a user description."""
    req_lower = user_request.lower()

    # 1. Infer category & template
    if any(k in req_lower for k in ("excel", "sheet", "xlsx", "csv", "table")):
        cat = ToolCategory.OFFICE.value
        base_risk = RiskLevel.LOW.value
        perms = ["files.read", "files.write"]
        inputs = {"type": "object", "properties": {"filepath": {"type": "string"}}, "required": ["filepath"]}
    elif any(k in req_lower for k in ("web", "url", "scrape", "http", "browser", "html")):
        cat = ToolCategory.BROWSER.value
        base_risk = RiskLevel.LOW.value
        perms = ["browser.read"]
        inputs = {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}
    elif any(k in req_lower for k in ("file", "rename", "move", "delete", "copy", "folder")):
        cat = ToolCategory.FILES.value
        base_risk = RiskLevel.MEDIUM.value if "delete" in req_lower else RiskLevel.LOW.value
        perms = ["files.read", "files.write"]
        inputs = {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}
    elif any(k in req_lower for k in ("api", "endpoint", "rest", "json")):
        cat = ToolCategory.BROWSER.value
        base_risk = RiskLevel.LOW.value
        perms = ["browser.read"]
        inputs = {"type": "object", "properties": {"endpoint": {"type": "string"}}, "required": ["endpoint"]}
    else:
        cat = ToolCategory.CORE.value
        base_risk = RiskLevel.SAFE.value
        perms = []
        inputs = {"type": "object", "properties": {"input_data": {"type": "string"}}, "required": ["input_data"]}

    # 2. Derive snake_case name
    if skill_name:
        derived_name = re.sub(r"[^a-z0-9_]+", "_", skill_name.lower()).strip("_")
    else:
        words = re.findall(r"[a-z0-9]+", req_lower)[:3]
        derived_name = "_".join(words) if words else "custom_skill"

    spec = {
        "name": derived_name,
        "version": "1.0.0",
        "description": user_request.strip(),
        "category": (category or cat).lower(),
        "risk": (risk or base_risk).upper(),
        "permissions": perms,
        "inputs": inputs,
        "outputs": {
            "type": "object",
            "properties": {
                "status": {"type": "string"},
                "output": {"type": "string"},
            },
        },
    }

    logger.info("skill_spec_drafted", name=derived_name, risk=spec["risk"], category=spec["category"])
    return spec
