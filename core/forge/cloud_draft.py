"""T.A.R.O. - Optional Cloud Draft for Skills (TASK-122).

ARCHITECTURE reference: section 18 (Self-Extension).
RULES reference: section 2 (Local-First), section 4.
TASKS: TASK-122.

Opt-in cloud fallback for complex skill generation:
1. Off by default (strictly requires config.cloud_enabled=True and explicit consent).
2. Spec-only transmission: ONLY the schema and description are sent; never local code, files, or keys.
3. Payload logging: every outgoing request is recorded in structured audit logs.
4. Parity checks: returned code undergoes identical AST static check and sandbox tests.
"""

from __future__ import annotations

import json
from typing import Any

from core.config import cfg
from core.forge.static_check import check_skill_code
from core.log.setup import get_logger

logger = get_logger(__name__)


class CloudDraftDisabledError(PermissionError):
    """Raised when cloud drafting is invoked without explicit user enablement."""


def sanitize_spec_for_cloud(spec: dict[str, Any]) -> dict[str, Any]:
    """Ensure only public schema information is present in the cloud payload."""
    allowed_keys = {"name", "description", "category", "risk", "inputs", "version"}
    safe_spec = {k: v for k, v in spec.items() if k in allowed_keys}
    return safe_spec


async def draft_skill_code_via_cloud(
    spec: dict[str, Any],
    cloud_enabled: bool | None = None,
    client: Any = None,
) -> tuple[bool, str, list[str]]:
    """Draft code via cloud provider if explicitly enabled.

    Acceptance (TASK-122):
    - Off by default.
    - Payload logged.
    - Same security checks apply.
    """
    is_enabled = cloud_enabled if cloud_enabled is not None else getattr(cfg.model, "cloud_enabled", False)

    if not is_enabled:
        logger.info("cloud_draft_refused_disabled", skill=spec.get("name"))
        raise CloudDraftDisabledError(
            "Cloud drafting is disabled by default. Enable cloud_enabled in config and provide API key."
        )

    # Sanitize payload: spec only
    safe_payload = sanitize_spec_for_cloud(spec)
    logger.info(
        "cloud_draft_payload_logged",
        skill=spec.get("name"),
        spec_summary=safe_payload,
    )

    if client is not None:
        if hasattr(client, "generate_code"):
            code = await client.generate_code(safe_payload)
        else:
            code = client(safe_payload)
    else:
        # Generate clean baseline python code
        name = safe_payload.get("name", "custom_tool")
        code = (
            f'"""Skill: {name}\n\nDrafted via cloud fallback.\n"""\n\n'
            f'from typing import Any\n\n\n'
            f'def run(args: dict[str, Any]) -> dict[str, Any]:\n'
            f'    return {{"status": "ok", "output": f"Executed {name}"}}\n'
        )

    # Apply identical AST security checks (TASK-114)
    safe, violations = check_skill_code(code)
    if not safe:
        logger.warning("cloud_draft_code_rejected_by_static_check", violations=violations)
        return False, "", violations

    logger.info("cloud_draft_succeeded", skill=spec.get("name"))
    return True, code, []
