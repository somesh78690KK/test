"""T.A.R.O. - Prompt builder with token budget.

ARCHITECTURE reference: section 6.4.
TASKS: TASK-014.

Assembles prompt sections into an array of ChatMessage objects while strictly
enforcing the 32,768-token context budget:
- System prompt: 1500 tokens
- Tool schemas: 4000 tokens (handled in registry/client)
- Profile and memory: 2000 tokens
- Rolling summary: 2000 tokens
- Recent turns: 20000 tokens
- Response reserve: 3268 tokens
"""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

from core.config import cfg
from core.log.setup import get_logger
from core.model.ollama_client import ChatMessage

logger = get_logger(__name__)


def estimate_tokens(text: str) -> int:
    """Rough token count estimator (approx. 4 characters per token)."""
    if not text:
        return 0
    return max(1, (len(text) + 3) // 4)


class PromptBuilder:
    """Constructs prompt messages conforming strictly to the token budget."""

    def __init__(self, persona_path: Path | str | None = None) -> None:
        self.persona_path = Path(persona_path or "config/persona.md")
        self.system_budget = cfg.prompt_budget.system
        self.profile_budget = cfg.prompt_budget.profile_and_memory
        self.summary_budget = cfg.prompt_budget.summary
        self.recent_turns_budget = cfg.prompt_budget.recent_turns

    def load_persona(self) -> str:
        """Loads and truncates the persona markdown to fit system budget."""
        if not self.persona_path.exists():
            return "You are T.A.R.O., an expert AI desktop assistant."
        try:
            content = self.persona_path.read_text(encoding="utf-8")
            return self._truncate_to_tokens(content, self.system_budget)
        except Exception as e:
            logger.error("persona_load_failed", error=str(e))
            return "You are T.A.R.O., an expert AI desktop assistant."

    def _truncate_to_tokens(self, text: str, max_tokens: int) -> str:
        """Truncates text to approximately fit within max_tokens."""
        if estimate_tokens(text) <= max_tokens:
            return text
        max_chars = max_tokens * 4
        return text[:max_chars].rstrip() + "\n...[truncated]"

    def build_system_message(
        self,
        profile_content: str = "",
        memory_content: str = "",
        summary_content: str = "",
    ) -> ChatMessage:
        """Assembles system prompt including persona, profile/memory, and rolling summary."""
        parts: list[str] = [self.load_persona()]

        # Profile and Memory
        pm_text = ""
        if profile_content:
            pm_text += f"\n\n### USER PROFILE\n{profile_content}"
        if memory_content:
            pm_text += f"\n\n### RECALLED MEMORY\n{memory_content}"
        if pm_text:
            parts.append(self._truncate_to_tokens(pm_text, self.profile_budget))

        # Rolling Summary of older conversation
        if summary_content:
            summary_section = f"\n\n### PREVIOUS CONVERSATION SUMMARY\n{summary_content}"
            parts.append(self._truncate_to_tokens(summary_section, self.summary_budget))

        full_system_text = "\n".join(parts)
        return ChatMessage(role="system", content=full_system_text)

    def fit_recent_turns(
        self,
        messages: Sequence[ChatMessage],
        max_tokens: int | None = None,
    ) -> list[ChatMessage]:
        """Trims older turns from the history so that recent turns stay within budget."""
        budget = max_tokens or self.recent_turns_budget
        fitted: list[ChatMessage] = []
        accumulated_tokens = 0

        # Iterate in reverse (most recent messages first)
        for msg in reversed(messages):
            msg_tokens = estimate_tokens(msg.content or "")
            if accumulated_tokens + msg_tokens > budget:
                break
            fitted.append(msg)
            accumulated_tokens += msg_tokens

        # Reverse back to chronological order
        fitted.reverse()
        return fitted

    def assemble(
        self,
        recent_messages: Sequence[ChatMessage],
        profile_content: str = "",
        memory_content: str = "",
        summary_content: str = "",
    ) -> list[ChatMessage]:
        """Assembles full list of ChatMessages ready for Ollama invocation."""
        system_msg = self.build_system_message(
            profile_content=profile_content,
            memory_content=memory_content,
            summary_content=summary_content,
        )
        fitted_turns = self.fit_recent_turns(recent_messages)
        return [system_msg, *fitted_turns]


default_prompt_builder = PromptBuilder()
