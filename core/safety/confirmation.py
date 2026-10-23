"""T.A.R.O. - Confirmation flow for risky actions.

ARCHITECTURE reference: section 8.
RULES reference: section 4.
TASKS: TASK-032.

Implements two-tiered confirmation:
- MEDIUM: yes / no (voice or text).
- HIGH / CRITICAL: requires typing or speaking the exact confirmation phrase.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Awaitable, Callable

from core.log.setup import get_logger
from core.safety.risk import RiskLevel

logger = get_logger(__name__)


@dataclass
class ConfirmationRequest:
    """Details of a tool execution requiring user confirmation."""

    tool_name: str
    risk: RiskLevel
    summary: str
    target: str
    exact_phrase: str | None = None
    timeout_s: float = 60.0


ConfirmationCallback = Callable[[ConfirmationRequest], Awaitable[bool]]


class ConfirmationGate:
    """Manages confirmation requests and phrase verification."""

    def __init__(self, callback: ConfirmationCallback | None = None) -> None:
        self.callback = callback

    def set_callback(self, callback: ConfirmationCallback) -> None:
        """Sets the UI or CLI confirmation callback."""
        self.callback = callback

    def generate_phrase(self, tool_name: str, target: str) -> str:
        """Generates the required confirmation phrase for HIGH/CRITICAL actions."""
        # Simple, deterministic phrase based on the action and target
        clean_target = target.replace("\\", "/").strip("/").split("/")[-1] or "target"
        return f"CONFIRM {tool_name.upper()} {clean_target}"

    def verify_response(
        self,
        risk: RiskLevel,
        expected_phrase: str | None,
        user_input: str,
    ) -> bool:
        """Verifies if the user's input fulfills the confirmation requirement.

        For MEDIUM: 'yes', 'y', 'ok', 'confirm' are accepted.
        For HIGH / CRITICAL: The user_input must match expected_phrase exactly (case-insensitive).
        """
        cleaned = user_input.strip()

        if risk == RiskLevel.MEDIUM:
            return cleaned.lower() in {"y", "yes", "confirm", "proceed", "ok"}

        if risk in (RiskLevel.HIGH, RiskLevel.CRITICAL):
            if not expected_phrase:
                return False
            return cleaned.upper() == expected_phrase.upper()

        return True

    async def request_confirmation(
        self,
        tool_name: str,
        risk: RiskLevel,
        summary: str,
        target: str = "",
        timeout_s: float = 60.0,
    ) -> bool:
        """Prompts the user for confirmation via registered callback or default."""
        exact_phrase = None
        if risk in (RiskLevel.HIGH, RiskLevel.CRITICAL):
            exact_phrase = self.generate_phrase(tool_name, target)

        req = ConfirmationRequest(
            tool_name=tool_name,
            risk=risk,
            summary=summary,
            target=target,
            exact_phrase=exact_phrase,
            timeout_s=timeout_s,
        )

        logger.info(
            "confirmation_requested",
            tool=tool_name,
            risk=risk.name,
            summary=summary,
            phrase=exact_phrase,
        )

        if self.callback is None:
            logger.warning("no_confirmation_callback_registered_denying")
            return False

        try:
            confirmed = await asyncio.wait_for(self.callback(req), timeout=timeout_s)
            logger.info("confirmation_result", tool=tool_name, confirmed=confirmed)
            return confirmed
        except asyncio.TimeoutError:
            logger.warning("confirmation_timed_out", tool=tool_name)
            return False
        except Exception as e:
            logger.error("confirmation_error", tool=tool_name, error=str(e))
            return False


# Global default gate
default_confirmation_gate = ConfirmationGate()
