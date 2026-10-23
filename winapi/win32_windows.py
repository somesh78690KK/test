"""T.A.R.O. - Windows Win32 window management adapter.

RULES reference: section 1, 2 (Only winapi/ may import pywin32).
TASKS: TASK-041.

Provides window control operations (minimize, maximize, restore, close,
switch, resize, get state) using pywin32 (win32gui, win32con), with graceful
mock fallback for testing or non-GUI/missing pywin32 environments.
"""

from __future__ import annotations

import os
from typing import Any

from core.log.setup import get_logger

logger = get_logger(__name__)

# Check pywin32 availability safely
_HAS_PYWIN32 = False
try:
    if os.name == "nt":
        import win32con
        import win32gui

        _HAS_PYWIN32 = True
except ImportError:
    _HAS_PYWIN32 = False

# State cache for mock or test environments
_MOCK_WINDOWS: dict[int, dict[str, Any]] = {
    1001: {
        "hwnd": 1001,
        "title": "Notepad - Untitled",
        "state": "normal",
        "visible": True,
        "rect": (100, 100, 800, 600),
    }
}


def find_windows(title_substr: str = "") -> list[dict[str, Any]]:
    """Returns a list of matching top-level windows with hwnd and title."""
    title_clean = title_substr.lower()

    if _HAS_PYWIN32:
        try:
            import win32gui

            results: list[dict[str, Any]] = []

            def _enum_cb(hwnd: int, extra: Any) -> None:
                if win32gui.IsWindowVisible(hwnd):
                    title = win32gui.GetWindowText(hwnd)
                    if title and (not title_clean or title_clean in title.lower()):
                        results.append({"hwnd": hwnd, "title": title})

            win32gui.EnumWindows(_enum_cb, None)
            return results
        except Exception as e:
            logger.warning("enum_windows_failed", error=str(e))
            return []

    return [
        {"hwnd": w["hwnd"], "title": w["title"]}
        for w in _MOCK_WINDOWS.values()
        if not title_clean or title_clean in w["title"].lower()
    ]


def get_window_state(hwnd: int) -> dict[str, Any]:
    """Returns current state of window (minimized, maximized, normal, visible, title, rect)."""
    if _HAS_PYWIN32 and hwnd not in _MOCK_WINDOWS:
        try:
            import win32con
            import win32gui

            if not win32gui.IsWindow(hwnd):
                return {"exists": False}

            title = win32gui.GetWindowText(hwnd)
            placement = win32gui.GetWindowPlacement(hwnd)
            show_cmd = placement[1]

            state = "normal"
            if show_cmd == win32con.SW_SHOWMINIMIZED:
                state = "minimized"
            elif show_cmd == win32con.SW_SHOWMAXIMIZED:
                state = "maximized"

            rect = win32gui.GetWindowRect(hwnd)
            visible = bool(win32gui.IsWindowVisible(hwnd))

            return {
                "exists": True,
                "hwnd": hwnd,
                "title": title,
                "state": state,
                "visible": visible,
                "rect": rect,
            }
        except Exception as e:
            logger.error("get_window_state_failed", hwnd=hwnd, error=str(e))
            return {"exists": False, "error": str(e)}

    win = _MOCK_WINDOWS.get(hwnd)
    if not win:
        return {"exists": False}
    return {"exists": True, **win}


def minimize_window(hwnd: int) -> bool:
    """Minimizes the given window."""
    if _HAS_PYWIN32 and hwnd not in _MOCK_WINDOWS:
        try:
            import win32con
            import win32gui

            win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)
            return True
        except Exception as e:
            logger.error("minimize_window_error", hwnd=hwnd, error=str(e))
            return False

    if hwnd in _MOCK_WINDOWS:
        _MOCK_WINDOWS[hwnd]["state"] = "minimized"
        return True
    return False


def maximize_window(hwnd: int) -> bool:
    """Maximizes the given window."""
    if _HAS_PYWIN32 and hwnd not in _MOCK_WINDOWS:
        try:
            import win32con
            import win32gui

            win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)
            return True
        except Exception as e:
            logger.error("maximize_window_error", hwnd=hwnd, error=str(e))
            return False

    if hwnd in _MOCK_WINDOWS:
        _MOCK_WINDOWS[hwnd]["state"] = "maximized"
        return True
    return False


def restore_window(hwnd: int) -> bool:
    """Restores the window to normal size."""
    if _HAS_PYWIN32 and hwnd not in _MOCK_WINDOWS:
        try:
            import win32con
            import win32gui

            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            return True
        except Exception as e:
            logger.error("restore_window_error", hwnd=hwnd, error=str(e))
            return False

    if hwnd in _MOCK_WINDOWS:
        _MOCK_WINDOWS[hwnd]["state"] = "normal"
        return True
    return False


def close_window(hwnd: int) -> bool:
    """Sends WM_CLOSE to the given window."""
    if _HAS_PYWIN32 and hwnd not in _MOCK_WINDOWS:
        try:
            import win32con
            import win32gui

            win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
            return True
        except Exception as e:
            logger.error("close_window_error", hwnd=hwnd, error=str(e))
            return False

    if hwnd in _MOCK_WINDOWS:
        del _MOCK_WINDOWS[hwnd]
        return True
    return False


def switch_to_window(hwnd: int) -> bool:
    """Brings window to the foreground."""
    if _HAS_PYWIN32 and hwnd not in _MOCK_WINDOWS:
        try:
            import win32gui

            win32gui.SetForegroundWindow(hwnd)
            return True
        except Exception as e:
            logger.error("switch_window_error", hwnd=hwnd, error=str(e))
            return False

    return hwnd in _MOCK_WINDOWS


def resize_window(hwnd: int, width: int, height: int) -> bool:
    """Resizes window to width and height."""
    if _HAS_PYWIN32 and hwnd not in _MOCK_WINDOWS:
        try:
            import win32con
            import win32gui

            rect = win32gui.GetWindowRect(hwnd)
            win32gui.MoveWindow(hwnd, rect[0], rect[1], width, height, True)
            return True
        except Exception as e:
            logger.error("resize_window_error", hwnd=hwnd, error=str(e))
            return False

    if hwnd in _MOCK_WINDOWS:
        r = _MOCK_WINDOWS[hwnd]["rect"]
        _MOCK_WINDOWS[hwnd]["rect"] = (r[0], r[1], width, height)
        return True
    return False
