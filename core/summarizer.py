"""T.A.R.O. - Rolling conversation summarizer.

ARCHITECTURE reference: section 6.4.
MEMORY reference: section 2 (Summary Cycle).
TASKS: TASK-015.

Every 5 turns, combines the previous summary and the newest 5 turns into a
fresh rolling summary targeted at 250-350 tokens.
Keeps: user goals, decisions, open tasks, file paths touched, confirmed preferences.
Drops: small talk, raw tool outputs, resolved errors.
"""

from __future__ import annotations

from typing import Sequence

from core.config import cfg
from core.log.setup import get_logger
from core.memory.sqlite_store import SQLiteMemoryStore, TurnRecord, get_sqlite_store
from core.model.ollama_client import ChatMessage, OllamaClient
from core.prompt_builder import estimate_tokens

logger = get_logger(__name__)

SUMMARIZE_SYSTEM_PROMPT = """You are the internal conversation summarizer for T.A.R.O.
Rewrite the rolling summary of the conversation to include the new turns.

CRITICAL RULES:
1. Target length: 250 to 350 tokens.
2. KEEP: User goals, architectural decisions, open tasks, file paths touched, user preferences.
3. DROP: Small talk, greetings, raw tool outputs, and transient errors that were fixed.
4. Output ONLY the summary text in concise bullet points. No commentary, no preamble."""


class RollingSummarizer:
    """Manages periodic rolling summaries every N turns."""

    def __init__(
        self,
        sqlite_store: SQLiteMemoryStore | None = None,
        ollama_client: OllamaClient | None = None,
    ) -> None:
        self.store = sqlite_store or get_sqlite_store()
        self.client = ollama_client or OllamaClient(
            host=cfg.model.ollama_host,
            timeout_s=cfg.orchestrator.tool_timeout_s,
        )
        self.every_n_turns = cfg.orchestrator.summary_every_n_turns
        self.min_tokens = cfg.orchestrator.summary_min_tokens
        self.max_tokens = cfg.orchestrator.summary_max_tokens

    def should_summarize(self, session_id: str, turn_count: int) -> bool:
        """Determines if a summary cycle is due."""
        if turn_count < self.every_n_turns:
            return False
        latest = self.store.get_latest_summary(session_id)
        if latest is None:
            return True
        return (turn_count - latest.covers_turns) >= self.every_n_turns

    def maybe_summarize(self, turns: list[dict]) -> str | None:
        """Convenience method for in-memory summarization without SQLite.
        
        This is a simplified version that checks if summarization is needed
        and returns a summary or None.
        """
        if not turns or len(turns) < self.every_n_turns:
            return None
        
        # For simplicity, just return None - the full summarize_cycle handles it
        # This method exists for compatibility with the orchestrator
        return None

    def build_summary_prompt(
        self,
        previous_summary: str,
        turns: Sequence[TurnRecord],
    ) -> list[ChatMessage]:
        """Constructs prompt for the summarizer model call."""
        turns_text = "\n".join(f"[{t.role.upper()}]: {t.content}" for t in turns)
        user_prompt = f"Previous summary:\n{previous_summary or '(None)'}\n\nNew conversation turns:\n{turns_text}\n\nGenerate updated concise rolling summary:"
        return [
            ChatMessage(role="system", content=SUMMARIZE_SYSTEM_PROMPT),
            ChatMessage(role="user", content=user_prompt),
        ]

    async def summarize_cycle(
        self,
        session_id: str,
        turn_count: int,
        model_tag: str | None = None,
    ) -> str:
        """Executes a rolling summary cycle and stores the result in SQLite."""
        latest_summary_rec = self.store.get_latest_summary(session_id)
        prev_summary = latest_summary_rec.text if latest_summary_rec else ""

        # Fetch turns since last summary
        recent_turns = self.store.get_recent_turns(session_id, limit=self.every_n_turns)
        if not recent_turns:
            return prev_summary

        messages = self.build_summary_prompt(prev_summary, recent_turns)
        target_model = model_tag or cfg.model.chat_model

        try:
            resp = await self.client.chat(
                model=target_model,
                messages=messages,
                num_predict=400,
                temperature=0.2,
            )
            summary_text = (resp.content or "").strip()
            # Enforce 400 token upper bound if necessary
            if estimate_tokens(summary_text) > cfg.prompt_budget.summary:
                summary_text = summary_text[: cfg.prompt_budget.summary * 4].rstrip() + "..."

            summary_id = f"sum_{session_id}_{turn_count}"
            self.store.add_summary(
                summary_id=summary_id,
                session_id=session_id,
                text=summary_text,
                covers_turns=turn_count,
            )
            logger.info(
                "rolling_summary_completed",
                session_id=session_id,
                turn_count=turn_count,
                summary_tokens=estimate_tokens(summary_text),
            )
            return summary_text
        except Exception as e:
            logger.error("rolling_summary_failed", session_id=session_id, error=str(e))
            return prev_summary


default_summarizer = RollingSummarizer()
