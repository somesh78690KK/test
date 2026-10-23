"""Tests for T.A.R.O. WebSocket subsystem & HUD Protocol (TASK-080, TASK-081, TASK-155)."""

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import aiohttp
from aiohttp import web

from core.ws.auth import SessionAuthManager
from core.ws.protocol import (
    MAX_MESSAGE_BYTES,
    ProtocolError,
    create_message,
    msg_chat_done,
    msg_chat_token,
    msg_confirm_request,
    msg_memory_deleted,
    msg_memory_entries,
    msg_settings_sync,
    msg_settings_updated,
    msg_state,
    msg_suggestion,
    msg_telemetry,
    msg_tool_activity,
    parse_message,
)
from core.ws.server import HUDServer
from core.ws.settings_manager import SettingsManager
from core.ws.accessibility import AccessibilityManager
from core.ws.memory_viewer import MemoryViewer


# --- TASK-081: Security & Auth Manager ---

def test_task_081_auth_manager_token_validation():
    """TASK-081: Token validation uses constant-time comparison; regenerates safely."""
    auth = SessionAuthManager()
    token = auth.token
    assert len(token) >= 32
    assert auth.validate_token(token) is True
    assert auth.validate_token("wrong-token-abc") is False
    assert auth.validate_token("") is False

    new_token = auth.regenerate_token()
    assert new_token != token
    assert auth.validate_token(new_token) is True
    assert auth.validate_token(token) is False


def test_task_081_host_header_guard():
    """TASK-081: Host header must be strictly 127.0.0.1 or localhost (DNS rebinding guard)."""
    auth = SessionAuthManager()
    assert auth.validate_host("127.0.0.1:8765") is True
    assert auth.validate_host("localhost:8765") is True
    assert auth.validate_host("127.0.0.1") is True
    assert auth.validate_host("localhost") is True
    assert auth.validate_host("attacker.com:8765") is False
    assert auth.validate_host("evil.com") is False
    assert auth.validate_host(None) is False


def test_task_081_origin_header_guard():
    """TASK-081: Origin header must be local or null."""
    auth = SessionAuthManager()
    assert auth.validate_origin("http://127.0.0.1:8765", expected_port=8765) is True
    assert auth.validate_origin("http://localhost:8765", expected_port=8765) is True
    assert auth.validate_origin("null") is True
    assert auth.validate_origin(None) is True
    assert auth.validate_origin("http://evil-site.com", expected_port=8765) is False
    assert auth.validate_origin("http://127.0.0.1:9999", expected_port=8765) is False


# --- TASK-081: Protocol Parser & Messages ---

def test_task_081_protocol_message_creation():
    """TASK-081: Message creation sets protocol version 1, unique id, and type."""
    msg = create_message("test_msg", data="abc")
    assert msg["v"] == 1
    assert "id" in msg
    assert msg["type"] == "test_msg"
    assert msg["data"] == "abc"


def test_task_081_protocol_parse_validation():
    """TASK-081: Parser validates JSON object and type field."""
    valid_raw = json.dumps({"type": "chat_send", "text": "hello"})
    parsed = parse_message(valid_raw)
    assert parsed["type"] == "chat_send"

    # Missing type field
    with pytest.raises(ProtocolError):
        parse_message(json.dumps({"text": "hello"}))

    # Not an object
    with pytest.raises(ProtocolError):
        parse_message(json.dumps(["hello"]))

    # Oversized payload
    oversized = "a" * (MAX_MESSAGE_BYTES + 10)
    with pytest.raises(ProtocolError):
        parse_message(oversized)


# --- TASK-080 & TASK-081: End-to-End HUD Server Test ---

@pytest.mark.asyncio
async def test_task_080_hud_server_http_and_ws_lifecycle(tmp_path: Path):
    """TASK-080: HUD server binds to 127.0.0.1, serves index HTML with bridge token."""
    html_file = tmp_path / "taro_hud.html"
    html_file.write_text("<!doctype html><html><head></head><body>HUD</body></html>", encoding="utf-8")

    auth = SessionAuthManager(token="test_secret_token_123")
    server = HUDServer(host="127.0.0.1", port=8799, auth_manager=auth, html_path=html_file)

    await server.start()
    assert server._running is True

    try:
        async with aiohttp.ClientSession() as session:
            # 1. Test HTTP GET / (Host valid)
            async with session.get("http://127.0.0.1:8799/") as resp:
                assert resp.status == 200
                text = await resp.text()
                assert "window.TARO_CONFIG" in text
                assert "test_secret_token_123" in text

            # 2. Test HTTP GET / with invalid Host header
            headers = {"Host": "attacker.com"}
            async with session.get("http://127.0.0.1:8799/", headers=headers) as resp:
                assert resp.status == 403

            # 3. Test WebSocket connection with wrong token -> closed with 4003
            async with session.ws_connect("http://127.0.0.1:8799/ws") as ws:
                await ws.send_json({"type": "auth", "token": "wrong_token"})
                msg = await ws.receive()
                # Should receive error and close
                assert msg.type in (aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.TEXT)

            # 4. Test WebSocket connection with valid token -> authenticated
            async with session.ws_connect("http://127.0.0.1:8799/ws") as ws:
                await ws.send_json({"type": "auth", "token": "test_secret_token_123"})

                # Initial messages sent on auth: state and models
                msg_state_resp = await ws.receive_json()
                assert msg_state_resp["type"] == "state"
                assert msg_state_resp["state"] == "idle"

                msg_models_resp = await ws.receive_json()
                assert msg_models_resp["type"] == "models_state"
                assert len(msg_models_resp["models"]) > 0

                # Test chat send turn
                await ws.send_json({"type": "chat_send", "text": "status check"})
                # Receive tokens and chat_done
                received_done = False
                for _ in range(50):
                    msg = await asyncio.wait_for(ws.receive_json(), timeout=3.0)
                    if msg.get("type") == "chat_done":
                        received_done = True
                        break
                assert received_done is True

    finally:
        await server.stop()
        assert server._running is False


# --- TASK-084: Tool Activity Masking ---

def test_task_084_tool_activity_masks_secrets():
    """TASK-084: Secret arguments are masked in tool activity events."""
    raw_args = {
        "api_key": "sk-1234567890abcdef",
        "user_password": "SuperSecretPassword123",
        "auth_token": "bearer-xyz-secret",
        "file_path": "C:\\workspace\\doc.txt",
    }
    msg = msg_tool_activity(
        tool_name="test_tool",
        status="running",
        args=raw_args,
        risk="SAFE",
    )
    assert msg["type"] == "tool_activity"
    masked = msg["args"]
    assert masked["api_key"] == "***MASKED***"
    assert masked["user_password"] == "***MASKED***"
    assert masked["auth_token"] == "***MASKED***"
    assert masked["file_path"] == "C:\\workspace\\doc.txt"


# --- TASK-085: Settings Manager ---

def test_task_085_settings_manager_sections(tmp_path: Path):
    """TASK-085: Settings manager provides read/write access to HUD config tabs."""
    mgr = SettingsManager()
    all_settings = mgr.get_all_settings()
    assert "general" in all_settings
    assert "voice" in all_settings
    assert "vision" in all_settings
    assert "models" in all_settings

    # Update a setting in memory/overrides
    mgr.set_setting("voice", "tts_engine", "pyttsx3")
    val = mgr.get_setting("voice", "tts_engine")
    assert val == "pyttsx3"


# --- TASK-086: Keyboard Shortcuts & Accessibility ---

def test_task_086_accessibility_and_shortcuts():
    """TASK-086: Accessibility manager maintains shortcuts and WCAG compliance states."""
    a11y = AccessibilityManager()
    shortcuts = a11y.get_shortcuts()
    assert len(shortcuts) > 0
    assert any(s["key"] == "Ctrl+Alt+F12" for s in shortcuts)
    assert any(s["action"] == "kill_switch" for s in shortcuts)

    # Register custom shortcut
    a11y.register_shortcut("Ctrl+Shift+X", "custom_action", "Execute custom action")
    updated = a11y.get_shortcuts()
    assert any(s["action"] == "custom_action" for s in updated)

    # Test accessibility flags
    assert a11y.high_contrast is False
    a11y.set_high_contrast(True)
    assert a11y.high_contrast is True

    assert a11y.reduced_motion is False
    a11y.set_reduced_motion(True)
    assert a11y.reduced_motion is True


# --- TASK-087: Memory Viewer (Delete Across Stores) ---

def test_task_087_memory_viewer_delete_across_stores(tmp_path: Path):
    """TASK-087: Memory viewer delete operation deletes from all three stores."""
    sqlite_file = tmp_path / "memory.db"
    import sqlite3
    conn = sqlite3.connect(str(sqlite_file))
    conn.execute("CREATE TABLE conversations (rowid INTEGER PRIMARY KEY, turn_id TEXT, user_prompt TEXT)")
    conn.execute("INSERT INTO conversations (rowid, turn_id, user_prompt) VALUES (42, 'turn-42', 'test prompt')")
    conn.commit()
    conn.close()

    json_dir = tmp_path / "json_memory"
    json_dir.mkdir()
    (json_dir / "42.json").write_text(json.dumps({"key": "val"}), encoding="utf-8")

    class MockChroma:
        def __init__(self):
            self.deleted_ids = []
        def delete(self, ids):
            self.deleted_ids.extend(ids)
        def count(self):
            return 1

    chroma = MockChroma()
    viewer = MemoryViewer(sqlite_path=sqlite_file, chroma_collection=chroma, json_dir=json_dir)

    # Delete entry "42"
    affected = viewer.delete_entry_all_stores("42")
    assert "sqlite" in affected
    assert "chroma" in affected
    assert "json" in affected
    assert not (json_dir / "42.json").exists()


# --- TASK-088: Proactive Suggestions ---

def test_task_088_proactive_suggestions():
    """TASK-088: Proactive suggestion message creation and fields."""
    msg = msg_suggestion("sug-1", "Would you like me to organize your desktop files?", confidence=0.85)
    assert msg["type"] == "suggestion"
    assert msg["suggestion_id"] == "sug-1"
    assert msg["confidence"] == 0.85

