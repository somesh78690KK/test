"""T.A.R.O. - Global kill switch.

ARCHITECTURE reference: section 8, 14.
RULES reference: section 4.
TASKS: TASK-036.

Stops running tools, subprocesses, and unloads model within 1 second.
Supported triggers:
1. RegisterHotKey / global keyboard hook (Ctrl+Alt+F12).
2. HUD / tray button.
3. CLI: `taro kill` or `python main.py kill`.
"""

from __future__ import annotations

import asyncio
import subprocess
import threading
from typing import Any, Callable

from core.log.setup import get_logger

logger = get_logger(__name__)

ProcessType = subprocess.Popen[Any] | asyncio.subprocess.Process


class KillSwitch:
    """Coordinates immediate termination and unloading across all subsystems."""

    def __init__(self) -> None:
        self._killed = threading.Event()
        self._async_killed: asyncio.Event | None = None
        self._registered_subprocesses: set[ProcessType] = set()
        self._callbacks: list[Callable[[], None]] = []
        self._async_callbacks: list[Callable[[], asyncio.Future[None] | None]] = []

    @property
    def is_killed(self) -> bool:
        """Returns True if kill switch has been triggered."""
        return self._killed.is_set()

    def reset(self) -> None:
        """Resets the kill switch flag for a new session."""
        self._killed.clear()
        if self._async_killed:
            self._async_killed.clear()

    def register_process(self, proc: ProcessType) -> None:
        """Registers a child subprocess to be terminated on kill."""
        self._registered_subprocesses.add(proc)

    def unregister_process(self, proc: ProcessType) -> None:
        """Removes a finished child subprocess."""
        self._registered_subprocesses.discard(proc)

    def on_kill(self, callback: Callable[[], None]) -> None:
        """Registers a synchronous callback to run on kill."""
        self._callbacks.append(callback)

    def trigger(self, source: str = "unknown") -> None:
        """Activates the kill switch synchronously."""
        if self._killed.is_set():
            return

        self._killed.set()
        logger.critical("kill_switch_triggered", source=source)

        # 1. Terminate all tracked child subprocesses
        for proc in list(self._registered_subprocesses):
            try:
                proc.terminate()
            except Exception as e:
                logger.error("kill_proc_error", pid=getattr(proc, "pid", None), error=str(e))

        # 2. Run registered cleanup callbacks
        for cb in self._callbacks:
            try:
                cb()
            except Exception as e:
                logger.error("kill_callback_error", error=str(e))

    async def trigger_async(self, source: str = "unknown") -> None:
        """Activates the kill switch asynchronously and unloads the model."""
        self.trigger(source=source)
        try:
            from core.model.model_manager import get_model_manager

            mm = get_model_manager()
            await mm.unload_all()
            logger.info("models_unloaded_by_kill_switch")
        except Exception as e:
            logger.warning("kill_model_unload_failed", error=str(e))


# Global singleton kill switch
kill_switch = KillSwitch()


def trigger_kill(source: str = "unknown") -> None:
    """Convenience function to trigger the global kill switch."""
    kill_switch.trigger(source=source)
