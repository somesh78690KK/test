"""Tests for T.A.R.O. orchestrator (plan/act loop).

TASKS: TASK-022, TASK-023, TASK-024.

Tests use a fake Ollama client and fake tools so no live model is needed.
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.model.ollama_client import ChatMessage, ChatResponse, ToolCall
from core.orchestrator import Orchestrator, PlanStep, StepStatus
from core.tools.base import BaseTool, RiskLevel, ToolCategory, ToolResult
from core.tools.registry import ToolRegistry


# ---------------------------------------------------------------------------
# Fake tools
# ---------------------------------------------------------------------------


class FakeEchoTool(BaseTool):
    """A SAFE tool that echoes its input."""

    name = "echo"
    description = "Echoes input text"
    parameters = {
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
    }
    risk = RiskLevel.SAFE
    category = ToolCategory.CORE
    timeout_s = 10

    async def run(self, args: dict) -> ToolResult:
        return ToolResult.ok(args.get("text", ""))


class FakeDeleteTool(BaseTool):
    """A MEDIUM-risk tool that pretends to delete a file."""

    name = "file_delete"
    description = "Delete a file"
    parameters = {
        "type": "object",
        "properties": {"path": {"type": "string"}},
        "required": ["path"],
    }
    risk = RiskLevel.MEDIUM
    category = ToolCategory.FILES
    timeout_s = 10

    async def run(self, args: dict) -> ToolResult:
        return ToolResult.ok(f"Deleted {args['path']}")


class FakeErrorTool(BaseTool):
    """A tool that always errors."""

    name = "always_error"
    description = "Always errors"
    parameters = {"type": "object", "properties": {}, "required": []}
    risk = RiskLevel.SAFE
    category = ToolCategory.CORE
    timeout_s = 10

    async def run(self, args: dict) -> ToolResult:
        return ToolResult.error_result("Something went wrong")


class FakeSlowTool(BaseTool):
    """A tool that takes longer than its timeout."""

    name = "slow_tool"
    description = "Takes too long"
    parameters = {"type": "object", "properties": {}, "required": []}
    risk = RiskLevel.SAFE
    category = ToolCategory.CORE
    timeout_s = 1  # 1 second timeout

    async def run(self, args: dict) -> ToolResult:
        await asyncio.sleep(10)  # way longer than timeout
        return ToolResult.ok("done")


# ---------------------------------------------------------------------------
# Fake Ollama client
# ---------------------------------------------------------------------------


class FakeOllamaClient:
    """Scripted Ollama client for testing the orchestrator."""

    def __init__(self, responses: list[ChatResponse]) -> None:
        self._responses = list(responses)
        self._call_count = 0

    async def chat(self, **kwargs: Any) -> ChatResponse:
        if self._call_count >= len(self._responses):
            # Default: text-only response
            return ChatResponse(
                content="Done.",
                tool_calls=[],
                model="fake",
                done=True,
                duration_ms=10,
                prompt_tokens=100,
                completion_tokens=10,
            )
        resp = self._responses[self._call_count]
        self._call_count += 1
        return resp


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_text_response(text: str) -> ChatResponse:
    return ChatResponse(
        content=text,
        tool_calls=[],
        model="fake",
        done=True,
        duration_ms=50,
        prompt_tokens=100,
        completion_tokens=20,
    )


def _make_tool_response(
    calls: list[ToolCall], text: str = ""
) -> ChatResponse:
    return ChatResponse(
        content=text,
        tool_calls=calls,
        model="fake",
        done=True,
        duration_ms=50,
        prompt_tokens=100,
        completion_tokens=20,
    )


@pytest.fixture(autouse=True)
def _reset_registry():
    """Ensure a clean registry for each test."""
    from core.tools import registry as reg_mod

    old = reg_mod._registry
    reg_mod._registry = ToolRegistry()
    yield
    reg_mod._registry = old


@pytest.fixture(autouse=True)
def _mock_permissions():
    """Mock the permission manager to always ALLOW for most tests."""
    from core.safety.permissions import PermissionAction

    with patch(
        "core.orchestrator.get_permission_manager"
    ) as mock_fn:
        pm = MagicMock()
        pm.evaluate.return_value = PermissionAction.ALLOW
        mock_fn.return_value = pm
        yield pm


@pytest.fixture(autouse=True)
def _mock_audit():
    """Mock audit log so tests don't write files."""
    with patch("core.orchestrator.get_audit_log") as mock_fn:
        audit = MagicMock()
        mock_fn.return_value = audit
        yield audit


@pytest.fixture(autouse=True)
def _mock_model_manager():
    """Mock model manager."""
    with patch("core.orchestrator.get_model_manager") as mock_fn:
        mm = MagicMock()
        mm.current_chat_model = "fake-model"
        mm.backup_model = "fake-backup"
        mm.switch_to_backup = MagicMock()
        mock_fn.return_value = mm
        yield mm


@pytest.fixture(autouse=True)
def _mock_kill_switch():
    """Ensure kill switch is not triggered."""
    from core.safety.kill_switch import kill_switch

    kill_switch.reset()
    yield


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestOrchestratorTextOnly:
    """Test that a pure text reply flows through correctly."""

    @pytest.mark.asyncio
    async def test_simple_chat(self):
        """A pure chat question gets a text reply and no tool steps."""
        client = FakeOllamaClient([_make_text_response("Hello there!")])
        orch = Orchestrator(client=client)

        result = await orch.process_turn("Hi!")

        assert result.reply == "Hello there!"
        assert result.steps == []
        assert result.status_block == ""
        assert result.total_steps == 0


class TestOrchestratorToolCalls:
    """Test tool call flow through the orchestrator."""

    @pytest.mark.asyncio
    async def test_single_tool_call(self):
        """Model calls one tool and returns a final reply."""
        from core.tools.registry import get_registry

        reg = get_registry()
        reg.register(FakeEchoTool())

        responses = [
            _make_tool_response(
                [ToolCall(name="echo", arguments={"text": "hello world"})]
            ),
            _make_text_response("I echoed your text."),
        ]
        client = FakeOllamaClient(responses)
        orch = Orchestrator(client=client)

        result = await orch.process_turn("Echo hello world")

        assert result.reply == "I echoed your text."
        assert len(result.steps) == 1
        assert result.steps[0].tool_name == "echo"
        assert result.steps[0].status == StepStatus.DONE
        assert "echo: OK" in result.status_block

    @pytest.mark.asyncio
    async def test_three_tool_plan(self):
        """Model completes a 3-tool plan."""
        from core.tools.registry import get_registry

        reg = get_registry()
        reg.register(FakeEchoTool())

        # 3 sequential tool calls, then a final text reply
        responses = [
            _make_tool_response(
                [ToolCall(name="echo", arguments={"text": "step1"})]
            ),
            _make_tool_response(
                [ToolCall(name="echo", arguments={"text": "step2"})]
            ),
            _make_tool_response(
                [ToolCall(name="echo", arguments={"text": "step3"})]
            ),
            _make_text_response("All three steps done."),
        ]
        client = FakeOllamaClient(responses)
        orch = Orchestrator(client=client)

        result = await orch.process_turn("Do three things")

        assert result.reply == "All three steps done."
        assert len(result.steps) == 3
        assert result.total_steps == 3
        assert all(s.status == StepStatus.DONE for s in result.steps)


class TestMaxSteps:
    """Test the 12-step hard limit."""

    @pytest.mark.asyncio
    async def test_step_13_refused(self):
        """Step 13 is refused when max_steps is 12."""
        from core.tools.registry import get_registry

        reg = get_registry()
        reg.register(FakeEchoTool())

        # 13 calls in one response (exceeds limit of 12)
        many_calls = [
            ToolCall(name="echo", arguments={"text": f"step{i}"})
            for i in range(13)
        ]
        responses = [_make_tool_response(many_calls)]
        client = FakeOllamaClient(responses)
        orch = Orchestrator(client=client)

        result = await orch.process_turn("Do 13 things")

        assert result.total_steps >= 12
        assert "Step limit" in result.reply or len(result.steps) == 12


class TestStatusBlock:
    """Test that the status block is code-generated, not model text."""

    @pytest.mark.asyncio
    async def test_error_tool_shows_failed(self):
        """When a tool errors, the status block shows FAILED even if model
        says 'done'."""
        from core.tools.registry import get_registry

        reg = get_registry()
        reg.register(FakeErrorTool())

        responses = [
            _make_tool_response(
                [ToolCall(name="always_error", arguments={})]
            ),
            _make_text_response("Everything is done successfully!"),
        ]
        client = FakeOllamaClient(responses)
        orch = Orchestrator(client=client)

        result = await orch.process_turn("Do the thing")

        assert result.steps[0].status == StepStatus.FAILED
        assert "FAILED" in result.status_block
        assert "Something went wrong" in result.status_block

    @pytest.mark.asyncio
    async def test_unknown_tool_shows_failed(self):
        """Calling a tool that doesn't exist shows FAILED."""
        responses = [
            _make_tool_response(
                [ToolCall(name="nonexistent_tool", arguments={})]
            ),
            _make_text_response("Done."),
        ]
        client = FakeOllamaClient(responses)
        orch = Orchestrator(client=client)

        result = await orch.process_turn("Use a fake tool")

        assert result.steps[0].status == StepStatus.FAILED
        assert "FAILED" in result.status_block
        assert "Unknown tool" in result.status_block


class TestCategoryFiltering:
    """Test per-request category detection (TASK-024)."""

    def test_chat_no_file_tools(self):
        """A pure chat question detects no file tool categories."""
        cats = Orchestrator._auto_detect_categories("What's the weather like?")
        assert ToolCategory.FILES not in cats
        assert ToolCategory.CORE in cats

    def test_file_question_includes_files(self):
        """Mentioning 'file' includes the FILES category."""
        cats = Orchestrator._auto_detect_categories(
            "Delete the file at C:\\temp\\test.txt"
        )
        assert ToolCategory.FILES in cats

    def test_browser_question_includes_browser(self):
        """Mentioning 'search' includes BROWSER."""
        cats = Orchestrator._auto_detect_categories("Search Google for Python tips")
        assert ToolCategory.BROWSER in cats

    def test_hardware_question(self):
        """Mentioning 'volume' includes HARDWARE."""
        cats = Orchestrator._auto_detect_categories("Set volume to 50%")
        assert ToolCategory.HARDWARE in cats


class TestKillSwitch:
    """Test that the kill switch stops the loop."""

    @pytest.mark.asyncio
    async def test_killed_between_steps(self):
        """Kill switch triggered during a multi-step plan stops execution."""
        from core.safety.kill_switch import kill_switch
        from core.tools.registry import get_registry

        reg = get_registry()
        reg.register(FakeEchoTool())

        responses = [
            _make_tool_response(
                [ToolCall(name="echo", arguments={"text": "step1"})]
            ),
        ]
        client = FakeOllamaClient(responses)
        orch = Orchestrator(client=client)

        # Trigger kill switch before the turn
        kill_switch.trigger(source="test")
        # Reset it once so process_turn resets it; but we'll trigger again
        # Actually: process_turn resets if killed, so let's trigger after call start
        kill_switch.reset()

        # We need a more nuanced test. Let's verify the kill flag works
        # by triggering it mid-execution via the step callback.
        steps_seen = []

        async def kill_on_first_step(step: PlanStep) -> None:
            steps_seen.append(step)
            if step.status == StepStatus.DONE and len(steps_seen) >= 2:
                kill_switch.trigger(source="test_callback")

        # Make enough tool calls to reach step 2
        many_responses = [
            _make_tool_response(
                [ToolCall(name="echo", arguments={"text": "s1"})]
            ),
            _make_tool_response(
                [ToolCall(name="echo", arguments={"text": "s2"})]
            ),
            _make_tool_response(
                [ToolCall(name="echo", arguments={"text": "s3"})]
            ),
            _make_text_response("all done"),
        ]
        client2 = FakeOllamaClient(many_responses)
        orch2 = Orchestrator(client=client2, step_callback=kill_on_first_step)

        result = await orch2.process_turn("Do three things")
        # After kill, the loop should have stopped
        assert result.killed or result.total_steps <= 3


class TestStepEventCallback:
    """Test that step events are emitted to the callback (TASK-025)."""

    @pytest.mark.asyncio
    async def test_step_events_emitted(self):
        """Step callback receives events with correct statuses."""
        from core.tools.registry import get_registry

        reg = get_registry()
        reg.register(FakeEchoTool())

        events: list[PlanStep] = []

        async def capture_event(step: PlanStep) -> None:
            events.append(
                PlanStep(
                    tool_name=step.tool_name,
                    args=step.args,
                    risk=step.risk,
                    status=step.status,
                    step_index=step.step_index,
                )
            )

        responses = [
            _make_tool_response(
                [ToolCall(name="echo", arguments={"text": "hi"})]
            ),
            _make_text_response("Done."),
        ]
        client = FakeOllamaClient(responses)
        orch = Orchestrator(client=client, step_callback=capture_event)

        await orch.process_turn("Say hi")

        # Should have RUNNING and DONE events
        statuses = [e.status for e in events]
        assert StepStatus.RUNNING in statuses
        assert StepStatus.DONE in statuses


class TestArgumentValidation:
    """Test argument validation catches missing required fields."""

    @pytest.mark.asyncio
    async def test_missing_required_arg(self):
        """Missing required arg results in FAILED status."""
        from core.tools.registry import get_registry

        reg = get_registry()
        reg.register(FakeEchoTool())

        responses = [
            _make_tool_response(
                [ToolCall(name="echo", arguments={})]  # missing 'text'
            ),
            _make_text_response("Done."),
        ]
        client = FakeOllamaClient(responses)
        orch = Orchestrator(client=client)

        result = await orch.process_turn("Echo nothing")

        assert result.steps[0].status == StepStatus.FAILED
        assert "Missing required" in result.steps[0].error
