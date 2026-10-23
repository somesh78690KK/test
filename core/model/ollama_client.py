"""T.A.R.O. - Ollama API client.

Wraps the Ollama HTTP API for streaming chat, tool-calling, and model
management. Never used directly by capabilities - goes through
core/model/model_manager.py.

ARCHITECTURE reference: sections 6.1, 6.2, 6.3.
TASKS: TASK-012.

Design decisions:
- Per-request ``think`` flag sent in the API body (not the Modelfile).
- Reasoning blocks (``<think>...</think>``) stripped before returning.
- One retry on 503 "model busy" or connection refused. No retry on other
  errors (they go to the caller as ModelError).
- Tool calls are returned as a list of ToolCall objects; the orchestrator
  does schema validation and one repair attempt.
"""

from __future__ import annotations

import asyncio
import json
import re
import time
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, cast

import httpx

from core.log import get_logger

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class ModelError(Exception):
    """Raised when the Ollama API returns an error or times out."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass
class ToolCall:
    """A single tool call requested by the model."""

    name: str
    arguments: dict


@dataclass
class ChatMessage:
    """A single message in the conversation."""

    role: str  # "user" | "assistant" | "tool" | "system"
    content: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_call_id: str | None = None
    name: str | None = None  # for tool result messages


@dataclass
class ChatResponse:
    """Final response from a chat call (non-streaming)."""

    content: str
    tool_calls: list[ToolCall]
    model: str
    done: bool
    duration_ms: int
    prompt_tokens: int
    completion_tokens: int


# ---------------------------------------------------------------------------
# Think-block stripper
# ---------------------------------------------------------------------------

_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


def _strip_think_blocks(text: str) -> str:
    """Remove <think>...</think> reasoning blocks before display.

    ARCHITECTURE section 6.2: reasoning blocks are stripped before display.
    """
    return _THINK_RE.sub("", text).strip()


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class OllamaClient:
    """Async Ollama API client.

    Args:
        host: Ollama server URL (default: ``http://127.0.0.1:11434``).
        timeout_s: Per-request timeout in seconds.
        max_retries: Number of retries on 503/connection-refused only.
    """

    def __init__(
        self,
        host: str = "http://127.0.0.1:11434",
        timeout_s: float = 120.0,
        max_retries: int = 2,
    ) -> None:
        self._host = host.rstrip("/")
        self._timeout = timeout_s
        self._max_retries = max_retries
        self._client = httpx.AsyncClient(
            base_url=self._host,
            timeout=httpx.Timeout(timeout_s, connect=5.0),
        )

    async def chat(
        self,
        model: str,
        messages: list[ChatMessage],
        tools: list[dict] | None = None,
        think: bool = False,
        temperature: float = 0.3,
        top_p: float = 0.9,
        num_ctx: int = 32768,
        num_predict: int = 2048,
        keep_alive: str = "10m",
    ) -> ChatResponse:
        """Send a chat request to Ollama and return the full response.

        Args:
            model: Model tag (e.g. ``"richardyoung/qwen3-8b-abliterated:Q4_K_M"``).
            messages: Conversation history as ChatMessage list.
            tools: JSON schemas for available tools (optional).
            think: Enable extended reasoning mode (strips blocks before return).
            temperature: Sampling temperature.
            top_p: Nucleus sampling probability.
            num_ctx: Context window size.
            num_predict: Max tokens to generate.
            keep_alive: How long to keep the model loaded after the request.

        Returns:
            A ChatResponse with the assistant's reply and any tool calls.

        Raises:
            ModelError: On timeout, connection failure, or API error.
        """
        payload = self._build_payload(
            model=model,
            messages=messages,
            tools=tools,
            think=think,
            temperature=temperature,
            top_p=top_p,
            num_ctx=num_ctx,
            num_predict=num_predict,
            keep_alive=keep_alive,
            stream=False,
        )

        start = time.monotonic()
        raw = await self._post_with_retry("/api/chat", payload)
        duration_ms = int((time.monotonic() - start) * 1000)

        return self._parse_response(raw, duration_ms)

    async def stream_chat(
        self,
        model: str,
        messages: list[ChatMessage],
        tools: list[dict] | None = None,
        think: bool = False,
        temperature: float = 0.3,
        top_p: float = 0.9,
        num_ctx: int = 32768,
        num_predict: int = 2048,
        keep_alive: str = "10m",
    ) -> AsyncIterator[str]:
        """Stream tokens from Ollama, yielding text chunks.

        Strips think blocks inline. Tool calls are not available in streaming
        mode - switch to ``chat()`` when tool schemas are provided.

        Args:
            model: Model tag.
            messages: Conversation history.
            tools: Not used in streaming mode.
            think: Enable reasoning (blocks stripped from stream).
            temperature: Sampling temperature.
            top_p: Nucleus sampling probability.
            num_ctx: Context window size.
            num_predict: Max tokens.
            keep_alive: Model keep-alive duration.

        Yields:
            Text chunk strings as they arrive.

        Raises:
            ModelError: On connection failure or API error.
        """
        payload = self._build_payload(
            model=model,
            messages=messages,
            tools=None,  # tools not used in stream path
            think=think,
            temperature=temperature,
            top_p=top_p,
            num_ctx=num_ctx,
            num_predict=num_predict,
            keep_alive=keep_alive,
            stream=True,
        )

        buffer = ""
        in_think = False

        try:
            async with self._client.stream("POST", "/api/chat", json=payload) as resp:
                if resp.status_code != 200:
                    body = await resp.aread()
                    raise ModelError(
                        f"Ollama stream error {resp.status_code}: {body.decode()}",
                        status_code=resp.status_code,
                    )

                async for line in resp.aiter_lines():
                    if not line:
                        continue
                    try:
                        chunk = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    token = chunk.get("message", {}).get("content", "")
                    buffer += token

                    # Strip think blocks from the stream
                    if not in_think:
                        start_idx = buffer.find("<think>")
                        if start_idx != -1:
                            # Yield everything before the think block
                            if start_idx > 0:
                                yield buffer[:start_idx]
                            buffer = buffer[start_idx:]
                            in_think = True
                        else:
                            # Safe to yield up to last 8 chars (guard against
                            # partial "<think>" at the boundary)
                            safe = max(0, len(buffer) - 8)
                            if safe > 0:
                                yield buffer[:safe]
                                buffer = buffer[safe:]
                    else:
                        end_idx = buffer.find("</think>")
                        if end_idx != -1:
                            buffer = buffer[end_idx + 8 :]
                            in_think = False

                    if chunk.get("done"):
                        break

            # Yield whatever remains
            if buffer and not in_think:
                yield buffer

        except httpx.TimeoutException as exc:
            raise ModelError(f"Ollama stream timed out: {exc}") from exc
        except httpx.ConnectError as exc:
            raise ModelError(f"Ollama connection refused: {exc}") from exc

    async def list_models(self) -> list[str]:
        """Return a list of locally available model tags.

        Raises:
            ModelError: On connection failure.
        """
        try:
            resp = await self._client.get("/api/tags")
            resp.raise_for_status()
            data = resp.json()
            return [m["name"] for m in data.get("models", [])]
        except httpx.HTTPError as exc:
            raise ModelError(f"Failed to list models: {exc}") from exc

    async def is_running(self) -> bool:
        """Return True if the Ollama server is reachable."""
        try:
            resp = await self._client.get("/", timeout=3.0)
            return resp.status_code < 500
        except httpx.HTTPError:
            return False

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_payload(
        self,
        model: str,
        messages: list[ChatMessage],
        tools: list[dict] | None,
        think: bool,
        temperature: float,
        top_p: float,
        num_ctx: int,
        num_predict: int,
        keep_alive: str,
        stream: bool,
    ) -> dict:
        """Assemble the Ollama chat API request payload."""
        msg_list = []
        for m in messages:
            entry: dict = {"role": m.role, "content": m.content}
            if m.tool_calls:
                entry["tool_calls"] = [
                    {"function": {"name": tc.name, "arguments": tc.arguments}}
                    for tc in m.tool_calls
                ]
            if m.name:
                entry["name"] = m.name
            msg_list.append(entry)

        payload: dict = {
            "model": model,
            "messages": msg_list,
            "stream": stream,
            "keep_alive": keep_alive,
            "options": {
                "temperature": temperature,
                "top_p": top_p,
                "num_ctx": num_ctx,
                "num_predict": num_predict,
            },
        }

        # think is sent in the top-level body, not in options
        if think:
            payload["think"] = True

        if tools:
            payload["tools"] = tools

        return payload

    async def _post_with_retry(self, path: str, payload: dict) -> dict:
        """POST to the given path, retrying on 503 or connection refused.

        Args:
            path: API path.
            payload: JSON payload.

        Returns:
            Parsed JSON response.

        Raises:
            ModelError: After exhausting retries.
        """
        last_exc: Exception | None = None
        for attempt in range(self._max_retries + 1):
            if attempt > 0:
                wait = 2 ** (attempt - 1)
                log.warning("ollama_retry", attempt=attempt, wait_s=wait, path=path)
                await asyncio.sleep(wait)

            try:
                resp = await self._client.post(path, json=payload)
                if resp.status_code == 503:
                    last_exc = ModelError(f"Ollama busy (503): {resp.text}", status_code=503)
                    continue
                if resp.status_code != 200:
                    raise ModelError(
                        f"Ollama error {resp.status_code}: {resp.text}",
                        status_code=resp.status_code,
                    )
                return cast(dict[str, Any], resp.json())

            except httpx.TimeoutException as exc:
                raise ModelError(f"Ollama request timed out after {self._timeout}s") from exc
            except (httpx.ConnectError, httpx.RemoteProtocolError) as exc:
                last_exc = ModelError(f"Ollama connection error: {exc}")
                continue
            except httpx.HTTPError as exc:
                raise ModelError(f"Ollama HTTP error: {exc}") from exc

        raise last_exc or ModelError("Ollama request failed after retries")

    def _parse_response(self, raw: dict, duration_ms: int) -> ChatResponse:
        """Parse a non-streaming Ollama API response."""
        msg = raw.get("message", {})
        content = _strip_think_blocks(msg.get("content", ""))

        raw_tool_calls = msg.get("tool_calls", [])
        tool_calls: list[ToolCall] = []
        for tc in raw_tool_calls:
            fn = tc.get("function", {})
            tool_calls.append(
                ToolCall(
                    name=fn.get("name", ""),
                    arguments=fn.get("arguments", {}),
                )
            )

        usage = raw.get("prompt_eval_count", 0), raw.get("eval_count", 0)

        return ChatResponse(
            content=content,
            tool_calls=tool_calls,
            model=raw.get("model", ""),
            done=raw.get("done", True),
            duration_ms=duration_ms,
            prompt_tokens=usage[0],
            completion_tokens=usage[1],
        )
