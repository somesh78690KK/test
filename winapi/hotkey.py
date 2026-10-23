"""T.A.R.O. - Global hotkey listener (Ctrl+Alt+F12 for kill switch).

ARCHITECTURE reference: section 8, 14.
TASKS: TASK-036.

Registers Ctrl+Alt+F12 globally using Windows RegisterHotKey in a dedicated thread
message pump, with graceful degradation.
"""

from __future__ import annotations

import ctypes
import os
import threading
from typing import Callable

from core.log.setup import get_logger
from core.safety.kill_switch import kill_switch

logger = get_logger(__name__)

# Windows virtual key codes and modifiers
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_NOREPEAT = 0x4000
VK_F12 = 0x7B
HOTKEY_ID_KILL = 1001


class GlobalHotkeyListener:
    """Runs a Windows message pump to catch global Ctrl+Alt+F12."""

    def __init__(self, callback: Callable[[], None] | None = None) -> None:
        self.callback = callback or (lambda: kill_switch.trigger(source="hotkey_ctrl_alt_f12"))
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._hwnd: int = 0

    def start(self) -> None:
        """Starts the hotkey thread."""
        if os.name != "nt":
            logger.info("hotkey_skipped_non_windows")
            return

        if self._thread and self._thread.is_alive():
            return

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, name="GlobalHotkeyThread", daemon=True)
        self._thread.start()
        logger.info("global_hotkey_listener_started", key="Ctrl+Alt+F12")

    def stop(self) -> None:
        """Stops the hotkey thread."""
        self._stop_event.set()
        # Post WM_QUIT to unblock GetMessage if on Windows
        if os.name == "nt" and self._thread and self._thread.is_alive():
            try:
                import win32api
                import win32con
                # Unregister
                win32api.PostQuitMessage(0)
            except Exception:
                pass
            self._thread.join(timeout=1.0)

    def _run_loop(self) -> None:
        """Dedicated message loop for RegisterHotKey."""
        try:
            import win32con
            import win32gui
            from ctypes import wintypes

            user32 = ctypes.windll.user32
            # Register Ctrl+Alt+F12
            modifiers = MOD_CONTROL | MOD_ALT | MOD_NOREPEAT
            registered = user32.RegisterHotKey(None, HOTKEY_ID_KILL, modifiers, VK_F12)

            if not registered:
                err = ctypes.GetLastError()
                logger.warning("register_hotkey_failed", error_code=err, hint="Elevated window or hotkey in use")
                return

            try:
                msg = wintypes.MSG()
                while not self._stop_event.is_set():
                    # PeekMessage or GetMessage
                    if user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 1):  # PM_REMOVE = 1
                        if msg.message == win32con.WM_HOTKEY:
                            if msg.wParam == HOTKEY_ID_KILL:
                                logger.critical("kill_switch_hotkey_pressed")
                                self.callback()
                        elif msg.message == win32con.WM_QUIT:
                            break
                        user32.TranslateMessage(ctypes.byref(msg))
                        user32.DispatchMessageW(ctypes.byref(msg))
                    else:
                        self._stop_event.wait(0.05)
            finally:
                user32.UnregisterHotKey(None, HOTKEY_ID_KILL)
                logger.info("global_hotkey_unregistered")

        except Exception as e:
            logger.error("hotkey_loop_exception", error=str(e))


default_hotkey_listener = GlobalHotkeyListener()
