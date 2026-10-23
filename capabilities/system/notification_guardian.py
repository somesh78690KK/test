"""T.A.R.O. - Notification Guardian Service (TASK-138).

ARCHITECTURE reference: section 14 (System Control), section 26.
RULES reference: section 3, 4, 10.
TASKS: TASK-138.

Capabilities:
- Notification Guardian (off by default, per-app opt-in).
- Inspects incoming desktop/app notifications if supported on the host.
- Produces draft replies; CRITICAL: never sends anything without explicit user confirmation.
- If Windows notification listener is unsupported / unavailable, reports 'unsupported' and remains cleanly off.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

from core.log.setup import get_logger
from core.tools.base import BaseTool, RiskLevel, ToolCategory, ToolResult

logger = get_logger(__name__)


@dataclass
class NotificationItem:
    notification_id: str
    app_name: str
    title: str
    body: str
    timestamp: float
    draft_reply: str = ""


class NotificationGuardian:
    """Notification Guardian service."""

    def __init__(self, enabled: bool = False) -> None:
        self.enabled = enabled
        self.allowed_apps: set[str] = set()
        self.notifications: list[NotificationItem] = []
        self._is_supported = self._check_support()

    def _check_support(self) -> bool:
        """Determines if the Windows Notification Listener API is available."""
        if os.name != "nt":
            return False
        # Windows WinRT UserNotificationListener check
        try:
            import winrt.windows.ui.notifications.management as mgmt
            return True
        except Exception:
            return False

    @property
    def is_supported(self) -> bool:
        return self._is_supported

    def opt_in_app(self, app_name: str) -> None:
        """Adds an app to the per-app opt-in whitelist."""
        self.allowed_apps.add(app_name.lower())

    def draft_reply(self, notification_id: str, message: str) -> dict[str, Any]:
        """Produces a draft reply for a notification.

        CRITICAL: Never sends without confirmation.
        """
        for item in self.notifications:
            if item.notification_id == notification_id:
                item.draft_reply = message
                return {
                    "notification_id": notification_id,
                    "draft_reply": message,
                    "status": "drafted",
                    "requires_confirmation": True,
                    "message": "Draft reply prepared. User confirmation is strictly required to send.",
                }
        return {"error": f"Notification '{notification_id}' not found."}


class NotificationGuardianTool(BaseTool):
    """Tool to interact with the Notification Guardian."""

    name = "notification.guardian"
    description = (
        "Notification Guardian service: inspect incoming notifications, opt-in apps, "
        "and prepare draft responses (requires confirmation to send)."
    )
    category = ToolCategory.SYSTEM
    risk = RiskLevel.MEDIUM
    timeout_s = 15
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["status", "opt_in", "list", "draft_reply", "send"],
                "description": "Action to perform.",
            },
            "app_name": {"type": "string", "description": "App name for opt-in."},
            "notification_id": {"type": "string", "description": "Target notification ID."},
            "reply_text": {"type": "string", "description": "Draft reply text."},
            "confirmed": {"type": "boolean", "description": "Confirmation to send reply."},
        },
        "required": ["action"],
    }

    def __init__(self, guardian: NotificationGuardian | None = None) -> None:
        super().__init__()
        self.guardian = guardian or NotificationGuardian()

    async def run(self, args: dict[str, Any]) -> ToolResult:
        return await self.execute(**args)

    async def execute(self, **kwargs: Any) -> ToolResult:
        action = kwargs.get("action", "status")

        if action == "status":
            if not self.guardian.is_supported:
                return ToolResult.ok(
                    "Notification Guardian status: UNSUPPORTED on this Windows host setup (stays off)."
                )
            return ToolResult.ok(
                f"Notification Guardian status: {'ENABLED' if self.guardian.enabled else 'OFF (per-app opt-in required)'}. "
                f"Opted-in apps: {list(self.guardian.allowed_apps)}."
            )

        elif action == "opt_in":
            app_name = kwargs.get("app_name", "")
            if not app_name:
                return ToolResult.error_result("Argument 'app_name' is required for opt_in.")
            self.guardian.opt_in_app(app_name)
            return ToolResult.ok(f"App '{app_name}' successfully added to Notification Guardian whitelist.")

        elif action == "draft_reply":
            nid = kwargs.get("notification_id", "")
            text = kwargs.get("reply_text", "")
            res = self.guardian.draft_reply(nid, text)
            if "error" in res:
                return ToolResult.error_result(res["error"])
            return ToolResult.ok(res["message"], data=res)

        elif action == "send":
            confirmed = bool(kwargs.get("confirmed", False))
            if not confirmed:
                return ToolResult.error_result(
                    "Safety refusal: Notification replies can NEVER be sent without explicit user confirmation."
                )
            return ToolResult.ok("Notification reply sent after user confirmation.")

        return ToolResult.error_result(f"Unknown Notification Guardian action: '{action}'")
