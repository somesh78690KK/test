"""T.A.R.O. - Reminders and timers capability.

ARCHITECTURE reference: section 14.
RULES reference: section 3, 10.
TASKS: TASK-052.

Schedules countdown timers and reminders that fire notifications and TTS messages.
"""

from __future__ import annotations

import asyncio
import datetime
import uuid
from dataclasses import dataclass
from typing import Any, Callable

from core.log.setup import get_logger
from core.tools.base import BaseTool, RiskLevel, ToolCategory, ToolResult

logger = get_logger(__name__)


@dataclass
class ActiveTimer:
    id: str
    message: str
    duration_s: float
    start_time: float
    end_time: float
    task: asyncio.Task[None] | None = None


class TimerManager:
    """Manages active timers and notification callbacks."""

    def __init__(self) -> None:
        self.timers: dict[str, ActiveTimer] = {}
        self.callbacks: list[Callable[[str, str], Any]] = []

    def on_fire(self, callback: Callable[[str, str], Any]) -> None:
        """Register callback: callback(timer_id, message)."""
        self.callbacks.append(callback)

    async def set_timer(self, duration_s: float, message: str) -> ActiveTimer:
        """Schedules a timer to fire after duration_s."""
        loop = asyncio.get_running_loop()
        timer_id = uuid.uuid4().hex[:6]
        now = loop.time()
        timer = ActiveTimer(
            id=timer_id,
            message=message,
            duration_s=duration_s,
            start_time=now,
            end_time=now + duration_s,
        )

        async def _countdown() -> None:
            try:
                await asyncio.sleep(duration_s)
                logger.info("timer_fired", timer_id=timer_id, message=message)
                for cb in self.callbacks:
                    try:
                        res = cb(timer_id, message)
                        if asyncio.iscoroutine(res):
                            await res
                    except Exception as e:
                        logger.error("timer_callback_error", error=str(e))
            except asyncio.CancelledError:
                logger.info("timer_cancelled", timer_id=timer_id)
            finally:
                self.timers.pop(timer_id, None)

        task = loop.create_task(_countdown())
        timer.task = task
        self.timers[timer_id] = timer
        return timer

    def cancel_timer(self, timer_id: str) -> bool:
        """Cancels an active timer."""
        timer = self.timers.pop(timer_id, None)
        if timer and timer.task:
            timer.task.cancel()
            return True
        return False


default_timer_manager = TimerManager()


class TimerSetTool(BaseTool):
    """Sets a timer or reminder."""

    name = "timer.set"
    description = "Set a timer or reminder for a given number of seconds with a message."
    category = ToolCategory.REMINDERS
    risk = RiskLevel.SAFE
    timeout_s = 5
    parameters = {
        "type": "object",
        "properties": {
            "duration_seconds": {
                "type": "number",
                "description": "Duration in seconds before timer fires.",
            },
            "message": {
                "type": "string",
                "description": "Message to display/speak when timer expires.",
            },
        },
        "required": ["duration_seconds", "message"],
    }

    async def run(self, args: dict) -> ToolResult:
        return await self.execute(**args)

    async def execute(self, **kwargs: Any) -> ToolResult:
        duration = float(kwargs.get("duration_seconds", 0))
        message = kwargs.get("message", "Timer finished!")

        if duration <= 0:
            return ToolResult(status="error", output="", error="duration_seconds must be > 0.")

        timer = await default_timer_manager.set_timer(duration, message)
        return ToolResult(
            status="ok",
            output=f"Timer [{timer.id}] set for {duration:.1f}s: '{message}'.",
        )


class TimerListTool(BaseTool):
    """Lists currently active timers."""

    name = "timer.list"
    description = "List all active countdown timers."
    category = ToolCategory.REMINDERS
    risk = RiskLevel.SAFE
    timeout_s = 5
    parameters = {"type": "object", "properties": {}}

    async def run(self, args: dict) -> ToolResult:
        return await self.execute(**args)

    async def execute(self, **kwargs: Any) -> ToolResult:
        if not default_timer_manager.timers:
            return ToolResult(status="ok", output="No active timers.")

        lines = ["Active timers:"]
        for tid, t in default_timer_manager.timers.items():
            lines.append(f"- ID: {tid} | Message: '{t.message}' | Duration: {t.duration_s}s")

        return ToolResult(status="ok", output="\n".join(lines))


TIMER_TOOLS: list[BaseTool] = [
    TimerSetTool(),
    TimerListTool(),
]
