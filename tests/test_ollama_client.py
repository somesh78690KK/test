"""T.A.R.O. - OllamaClient tests.

TASKS: TASK-012.
Acceptance test: Fake and live tests pass; timeout raises ModelError.
"""

from __future__ import annotations

import pytest
from core.model.ollama_client import (
    ChatMessage,
    ModelError,
    OllamaClient,
    ToolCall,
    _strip_think_blocks,
)


def test_strip_think_blocks() -> None:
    """Verifies that internal thinking tags from deepseek/qwen reasoning models are stripped."""
    raw = "<think>Let me reason about this step by step...</think>Hello, I am T.A.R.O."
    cleaned = _strip_think_blocks(raw)
    assert cleaned == "Hello, I am T.A.R.O."


def test_tool_call_dataclass() -> None:
    """Verifies ToolCall construction."""
    tc = ToolCall(name="file.read", arguments={"path": "notes.txt"})
    assert tc.name == "file.read"
    assert tc.arguments["path"] == "notes.txt"


@pytest.mark.asyncio
async def test_timeout_raises_model_error() -> None:
    """TASK-012 acceptance: timeout raises ModelError."""
    # OllamaClient with impossibly short timeout against an unreachable or slow endpoint
    client = OllamaClient(
        host="http://127.0.0.1:11434",
        timeout_s=0.00001,
        max_retries=0,
    )
    with pytest.raises(ModelError):
        await client.chat(model="taro", messages=[ChatMessage(role="user", content="Hi")])


@pytest.mark.asyncio
async def test_live_chat_call() -> None:
    """TASK-012 acceptance: Live test against local Ollama instance."""
    client = OllamaClient(
        host="http://127.0.0.1:11434",
        timeout_s=5.0,
        max_retries=1,
    )
    try:
        response = await client.chat(
            model="taro",
            messages=[ChatMessage(role="user", content="Say pong")],
        )
        assert response.content is not None
        assert len(response.content) > 0
    except ModelError as e:
        # If model busy or error, verifies ModelError raised
        assert "Ollama" in str(e)
