"""T.A.R.O. - Untrusted content wrapper and taint tracking.

ARCHITECTURE reference: section 23.
RULES reference: section 4.
TASKS: TASK-039.

Wraps content from web, files, OCR, notifications, and tool output as untrusted.
Tracks taint across a turn: if untrusted content entered context, any MEDIUM,
HIGH, or CRITICAL action cannot be auto-executed or bypassed by trusted-action lists,
and must display the untrusted source on the confirmation card.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from core.log.setup import get_logger

logger = get_logger(__name__)


class UntrustedSource(StrEnum):
    WEB = "web"
    FILE = "file"
    OCR = "ocr"
    NOTIFICATION = "notification"
    TOOL = "tool"
    CLIPBOARD = "clipboard"


@dataclass
class TaintContext:
    """Tracks whether untrusted content has entered the current turn."""

    sources: set[str] = field(default_factory=set)

    @property
    def is_tainted(self) -> bool:
        """Returns True if any untrusted source has contributed to the current turn."""
        return len(self.sources) > 0

    def add_source(self, source: UntrustedSource | str) -> None:
        """Marks context as tainted with the given source."""
        s = source.value if isinstance(source, UntrustedSource) else str(source)
        self.sources.add(s)
        logger.info("taint_source_added", source=s, total_sources=list(self.sources))

    def clear(self) -> None:
        """Clears taint for a new turn/request."""
        self.sources.clear()

    def get_source_warning(self) -> str:
        """Returns the mandatory warning message for confirmation cards."""
        if not self.is_tainted:
            return ""
        sources_str = ", ".join(sorted(self.sources))
        return f"This request involved untrusted content from: {sources_str}."


def wrap_untrusted(text: str, source: UntrustedSource | str) -> str:
    """Wraps text in an untrusted XML tag.

    Rule: The system prompt treats <untrusted> tags as pure data, never instructions.
    """
    s = source.value if isinstance(source, UntrustedSource) else str(source)
    # Sanitize closing tag inside text to prevent tag injection breakout
    safe_text = text.replace("</untrusted>", "&lt;/untrusted&gt;")
    return f'<untrusted source="{s}">\n{safe_text}\n</untrusted>'


# Global turn taint context
current_turn_taint = TaintContext()
