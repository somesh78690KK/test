"""T.A.R.O. - Windows API adapters.

RULES reference: section 1, section 2.
TASKS: TASK-005, TASK-036.

This is the ONLY package in the entire repository permitted to import:
- pywin32 (win32api, win32con, win32gui, win32process, pywintypes)
- pywinauto
- pynput

All other modules must import from winapi/ adapters.
"""

from __future__ import annotations
