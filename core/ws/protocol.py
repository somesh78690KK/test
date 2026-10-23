"""T.A.R.O. - WebSocket protocol definitions and message schemas (TASK-081).

ARCHITECTURE reference: section 27 (HUD Protocol).
RULES reference: section 15.
TASKS: TASK-081.

All messages are JSON objects containing:
  - v (int): Protocol version (1).
  - id (str): Unique message ID.
  - type (str): Message type name.
  - payload fields according to message type.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

PROTOCOL_VERSION = 1
MAX_MESSAGE_BYTES = 1024 * 1024  # 1 MB limit


class ProtocolError(Exception):
    """Raised when an invalid or malformed protocol message is received."""


def create_message(msg_type: str, **kwargs: Any) -> dict[str, Any]:
    """Construct a standard T.A.R.O. protocol message."""
    msg_id = kwargs.pop("id", None) or str(uuid.uuid4())
    return {
        "v": PROTOCOL_VERSION,
        "id": msg_id,
        "type": msg_type,
        **kwargs,
    }


def parse_message(raw_data: str | bytes) -> dict[str, Any]:
    """Parse and validate incoming raw message JSON.

    Enforces:
    - Maximum message size (1 MB)
    - Valid JSON object
    - Required fields ('type')
    """
    if len(raw_data) > MAX_MESSAGE_BYTES:
        raise ProtocolError(f"Message exceeds maximum size limit of {MAX_MESSAGE_BYTES} bytes.")

    try:
        data = json.loads(raw_data)
    except Exception as e:
        raise ProtocolError(f"Invalid JSON payload: {e}")

    if not isinstance(data, dict):
        raise ProtocolError("Protocol message must be a JSON object.")

    if "type" not in data or not isinstance(data["type"], str):
        raise ProtocolError("Protocol message is missing required 'type' string field.")

    return data


# --- Message Helper Constructors ---

def msg_auth(token: str) -> dict[str, Any]:
    return create_message("auth", token=token)


def msg_state(state: str) -> dict[str, Any]:
    valid = ("idle", "listening", "speaking", "thinking")
    if state not in valid:
        state = "idle"
    return create_message("state", state=state)


def msg_audio_level(source: str, level: float) -> dict[str, Any]:
    clamped = max(0.0, min(1.0, float(level)))
    return create_message("audio_level", source=source, level=round(clamped, 3))


def msg_chat_token(message_id: str, text: str) -> dict[str, Any]:
    return create_message("chat_token", message_id=message_id, text=text)


def msg_chat_done(message_id: str, ts: str, status_block: str = "") -> dict[str, Any]:
    return create_message("chat_done", message_id=message_id, ts=ts, status_block=status_block)


def msg_telemetry(
    cpu: float,
    ram: float,
    gpu: float,
    vram: float,
    disk: float,
    temp: float,
    net_down: float,
    net_up: float,
    ping: float = 15.0,
) -> dict[str, Any]:
    return create_message(
        "telemetry",
        cpu=round(cpu, 1),
        ram=round(ram, 2),
        gpu=round(gpu, 1),
        vram=round(vram, 2),
        disk=round(disk, 1),
        temp=round(temp, 1),
        net_down=round(net_down, 1),
        net_up=round(net_up, 1),
        ping=round(ping, 1),
    )


def msg_models_state(models: list[dict[str, Any]]) -> dict[str, Any]:
    return create_message("models_state", models=models)


def msg_confirm_request(
    request_id: str,
    risk: str,
    action: str,
    target: str,
    reason: str,
    source: str = "",
    phrase: str = "",
) -> dict[str, Any]:
    return create_message(
        "confirm_request",
        request_id=request_id,
        risk=risk,
        action=action,
        target=target,
        reason=reason,
        source=source,
        phrase=phrase,
    )


def msg_camera_frame(jpeg_b64: str) -> dict[str, Any]:
    return create_message("camera_frame", jpeg_b64=jpeg_b64)


def msg_error(code: str, message: str, next_step: str = "") -> dict[str, Any]:
    return create_message("error", code=code, message=message, next_step=next_step)


# --- Phase 7 Additional Messages (TASK-084 to TASK-088) ---

SECRET_PATTERNS = {"api_key", "token", "password", "secret", "credential", "auth"}


def _mask_args(args: dict[str, Any]) -> dict[str, Any]:
    """Mask secret argument values in tool activity display."""
    masked = {}
    for k, v in args.items():
        if any(pattern in k.lower() for pattern in SECRET_PATTERNS):
            masked[k] = "***MASKED***"
        elif isinstance(v, str) and len(v) > 200:
            masked[k] = v[:100] + "...[truncated]"
        else:
            masked[k] = v
    return masked


def msg_tool_activity(
    tool_name: str,
    status: str,
    args: dict[str, Any] | None = None,
    output: str = "",
    error: str = "",
    duration_ms: int = 0,
    risk: str = "SAFE",
    step_index: int = 0,
) -> dict[str, Any]:
    """TASK-084: Tool activity panel with expandable rows, secret args masked."""
    safe_args = _mask_args(args) if args else {}
    return create_message(
        "tool_activity",
        tool_name=tool_name,
        status=status,
        args=safe_args,
        output=output[:500] if output else "",
        error=error,
        duration_ms=duration_ms,
        risk=risk,
        step_index=step_index,
    )


def msg_settings_sync(settings: dict[str, Any]) -> dict[str, Any]:
    """TASK-085: Send current settings state to HUD."""
    return create_message("settings_sync", settings=settings)


def msg_settings_updated(section: str, key: str, value: Any) -> dict[str, Any]:
    """TASK-085: Notify HUD that a setting was updated."""
    return create_message("settings_updated", section=section, key=key, value=value)


def msg_memory_entries(
    entries: list[dict[str, Any]],
    store: str = "all",
    total: int = 0,
) -> dict[str, Any]:
    """TASK-087: Memory viewer entries for HUD display."""
    return create_message("memory_entries", entries=entries, store=store, total=total)


def msg_memory_deleted(entry_id: str, stores: list[str]) -> dict[str, Any]:
    """TASK-087: Confirm memory entry deletion across stores."""
    return create_message("memory_deleted", entry_id=entry_id, stores=stores)


def msg_suggestion(
    suggestion_id: str,
    text: str,
    confidence: float = 0.5,
    category: str = "general",
) -> dict[str, Any]:
    """TASK-088: Proactive suggestion card (never executes without confirmation)."""
    return create_message(
        "suggestion",
        suggestion_id=suggestion_id,
        text=text,
        confidence=round(confidence, 2),
        category=category,
        requires_confirmation=True,  # always True per ARCHITECTURE
    )


def msg_keyboard_shortcuts(shortcuts: list[dict[str, str]]) -> dict[str, Any]:
    """TASK-086: Send available keyboard shortcuts to HUD."""
    return create_message("keyboard_shortcuts", shortcuts=shortcuts)
