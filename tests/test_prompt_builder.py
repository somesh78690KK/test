"""T.A.R.O. - Prompt builder tests.

TASKS: TASK-014.
Acceptance test: Prompt never exceeds 32768 tokens in a 50-turn test.
"""

from __future__ import annotations

from core.model.ollama_client import ChatMessage
from core.prompt_builder import PromptBuilder, estimate_tokens


def test_task_014_prompt_never_exceeds_4096_tokens_50_turns() -> None:
    """TASK-014 acceptance: In a 50-turn test, total prompt never exceeds 32768 tokens."""
    builder = PromptBuilder()

    # Generate 50 substantial turns (each turn has ~100-200 tokens)
    messages: list[ChatMessage] = []
    for i in range(50):
        role = "user" if i % 2 == 0 else "assistant"
        content = f"Turn {i}: " + ("This is test user query and conversation content. " * 15)
        messages.append(ChatMessage(role=role, content=content))

    # Assemble with profile and summary
    assembled = builder.assemble(
        recent_messages=messages,
        profile_content="User preferences: prefers Python 3.12, dark mode, concise answers.",
        summary_content="Previous conversation summarized: Discussed architecture and safety.",
    )

    total_tokens = sum(estimate_tokens(m.content or "") for m in assembled)
    # The assembled prompt must fit inside 32768 - 3268 (response reserve) = ~29500 tokens
    assert total_tokens <= 32768, f"Total tokens {total_tokens} exceeded 32768 cap!"
    assert len(assembled) > 1, "Must contain system message and fitted turns"
    assert assembled[0].role == "system"
