"""T.A.R.O. - Risk classifier.

Computes the effective risk of a tool call. Base risk comes from the tool
definition. Arguments can escalate it (e.g., paths under C:\\Windows -> CRITICAL).

ARCHITECTURE reference: section 8.
RULES reference: section 4.
TASKS: TASK-030.

Key rule: risk comes from CODE, never from model output. The model's stated
risk is advisory only. This function is the ground truth.
"""

from __future__ import annotations

import re
from typing import Any

from core.tools.base import RiskLevel

# ---------------------------------------------------------------------------
# Windows system path patterns - CRITICAL if targeted
# ---------------------------------------------------------------------------

_CRITICAL_PATH_PATTERNS = [
    re.compile(r"^[Cc]:\\[Ww][Ii][Nn][Dd][Oo][Ww][Ss]", re.IGNORECASE),
    re.compile(r"^[Cc]:\\[Pp]rogram [Ff]iles", re.IGNORECASE),
    re.compile(r"^[Cc]:\\[Pp]rogram[Dd]ata", re.IGNORECASE),
    re.compile(r"^[Cc]:\\[Ss]ystem", re.IGNORECASE),
    # Registry hives
    re.compile(r"^HKEY_LOCAL_MACHINE", re.IGNORECASE),
    re.compile(r"^HKLM", re.IGNORECASE),
]

_HIGH_PATH_PATTERNS = [
    re.compile(r"^[Cc]:\\[Uu]sers\\[^\\]+\\[Aa]pp[Dd]ata", re.IGNORECASE),
    # Dotfiles and config
    re.compile(r"\\\.env$", re.IGNORECASE),
    re.compile(r"\\config\\", re.IGNORECASE),
]

# Shell operations that escalate risk
_CRITICAL_SHELL_KEYWORDS = ["rm -rf", "del /f /s /q", "format", "diskpart", "bcdedit"]
_HIGH_SHELL_KEYWORDS = ["netsh", "sc ", "reg delete", "sfc ", "dism "]


def classify_risk(
    base_risk: RiskLevel,
    tool_name: str,
    args: dict[str, Any],
) -> RiskLevel:
    """Compute the effective risk of a tool call.

    Args:
        base_risk: The tool's declared base risk.
        tool_name: Tool name for context-specific rules.
        args: The arguments passed to the tool.

    Returns:
        Effective RiskLevel (may be higher than base_risk, never lower).
    """
    effective = base_risk

    # Inspect string arguments for dangerous paths and commands
    for key, value in args.items():
        if not isinstance(value, str):
            continue

        escalated = _escalate_for_path(value)
        if escalated and escalated > effective:
            effective = escalated

        escalated = _escalate_for_shell_command(value, tool_name)
        if escalated and escalated > effective:
            effective = escalated

    # Specific tool escalation rules
    if tool_name in ("file.delete", "file.overwrite", "explorer.delete_permanent"):
        if effective < RiskLevel.HIGH:
            effective = RiskLevel.HIGH

    if tool_name == "explorer.delete_permanent":
        effective = RiskLevel.CRITICAL

    if tool_name in ("process.terminate", "hardware.shutdown"):
        if effective < RiskLevel.HIGH:
            effective = RiskLevel.HIGH

    return effective


def _escalate_for_path(value: str) -> RiskLevel | None:
    """Check a string value for dangerous path patterns."""
    # Normalize path separators
    normalized = value.replace("/", "\\")

    for pattern in _CRITICAL_PATH_PATTERNS:
        if pattern.search(normalized):
            return RiskLevel.CRITICAL

    for pattern in _HIGH_PATH_PATTERNS:
        if pattern.search(normalized):
            return RiskLevel.HIGH

    return None


def _escalate_for_shell_command(value: str, tool_name: str) -> RiskLevel | None:
    """Check shell command arguments for dangerous patterns."""
    if "shell" not in tool_name.lower() and "code" not in tool_name.lower():
        return None

    lower = value.lower()
    for kw in _CRITICAL_SHELL_KEYWORDS:
        if kw.lower() in lower:
            return RiskLevel.CRITICAL

    for kw in _HIGH_SHELL_KEYWORDS:
        if kw.lower() in lower:
            return RiskLevel.HIGH

    return None


class RiskClassifier:
    """Classifies effective risk for tool calls."""

    def classify(
        self,
        base_risk: RiskLevel,
        tool_name: str,
        args: dict[str, Any],
    ) -> RiskLevel:
        return classify_risk(base_risk, tool_name, args)


default_risk_classifier = RiskClassifier()
compute_effective_risk = classify_risk
