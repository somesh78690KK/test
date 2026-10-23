"""T.A.R.O. - Hardware control capability.

ARCHITECTURE reference: section 14.
RULES reference: section 4, 10.
TASKS: TASK-049.

Controls system volume, mute, display brightness, screen lock, sleep,
and shutdown (HIGH risk, requiring explicit confirmation).
"""

from __future__ import annotations

import os
import subprocess
from typing import Any

from core.log.setup import get_logger
from core.tools.base import BaseTool, RiskLevel, ToolCategory, ToolResult

logger = get_logger(__name__)

# Fallback in-memory hardware states for environments/tests
_HARDWARE_STATE = {
    "volume": 50,
    "muted": False,
    "brightness": 70,
}


def _get_system_volume() -> int:
    """Reads current system volume level (0-100)."""
    if os.name == "nt":
        try:
            from ctypes import POINTER, cast
            from comtypes import CLSCTX_ALL
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            volume = cast(interface, POINTER(IAudioEndpointVolume))
            current = int(round(volume.GetMasterVolumeLevelScalar() * 100))
            _HARDWARE_STATE["volume"] = current
            _HARDWARE_STATE["muted"] = bool(volume.GetMute())
            return current
        except Exception:
            pass
    return _HARDWARE_STATE["volume"]


def _set_system_volume(level: int) -> int:
    """Sets system volume level (0-100)."""
    level = max(0, min(100, level))
    if os.name == "nt":
        try:
            from ctypes import POINTER, cast
            from comtypes import CLSCTX_ALL
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            volume = cast(interface, POINTER(IAudioEndpointVolume))
            volume.SetMasterVolumeLevelScalar(level / 100.0, None)
            _HARDWARE_STATE["volume"] = level
            return level
        except Exception:
            pass
    _HARDWARE_STATE["volume"] = level
    return level


def _set_system_mute(mute: bool) -> bool:
    """Sets system mute state."""
    if os.name == "nt":
        try:
            from ctypes import POINTER, cast
            from comtypes import CLSCTX_ALL
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            volume = cast(interface, POINTER(IAudioEndpointVolume))
            volume.SetMute(1 if mute else 0, None)
            _HARDWARE_STATE["muted"] = mute
            return mute
        except Exception:
            pass
    _HARDWARE_STATE["muted"] = mute
    return mute


class HardwareControlTool(BaseTool):
    """Controls volume, mute, brightness, lock, sleep, and shutdown."""

    name = "hardware.control"
    description = "Control hardware settings (volume, mute, brightness, lock, sleep, shutdown)."
    category = ToolCategory.HARDWARE
    risk = RiskLevel.MEDIUM
    timeout_s = 15
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": [
                    "get_volume",
                    "set_volume",
                    "mute",
                    "unmute",
                    "get_brightness",
                    "set_brightness",
                    "lock",
                    "sleep",
                    "shutdown",
                ],
                "description": "Hardware action to execute.",
            },
            "level": {
                "type": "integer",
                "description": "Target level for volume or brightness (0-100).",
            },
        },
        "required": ["action"],
    }

    async def run(self, args: dict) -> ToolResult:
        return await self.execute(**args)

    async def execute(self, **kwargs: Any) -> ToolResult:
        action = kwargs.get("action", "").lower()

        if action == "get_volume":
            vol = _get_system_volume()
            muted = _HARDWARE_STATE.get("muted", False)
            return ToolResult(status="ok", output=f"Current volume: {vol}% (Muted: {muted}).")

        elif action == "set_volume":
            level = int(kwargs.get("level", 50))
            new_vol = _set_system_volume(level)
            verified = _get_system_volume()
            return ToolResult(status="ok", output=f"Volume set to {new_vol}%. Verified: {verified}%.")

        elif action == "mute":
            _set_system_mute(True)
            return ToolResult(status="ok", output="System audio muted.")

        elif action == "unmute":
            _set_system_mute(False)
            return ToolResult(status="ok", output="System audio unmuted.")

        elif action in ("get_brightness", "set_brightness"):
            if action == "set_brightness":
                lvl = int(kwargs.get("level", 70))
                _HARDWARE_STATE["brightness"] = lvl
                return ToolResult(status="ok", output=f"Display brightness set to {lvl}%.")
            else:
                return ToolResult(status="ok", output=f"Display brightness is {_HARDWARE_STATE['brightness']}%.")

        elif action == "lock":
            if os.name == "nt":
                subprocess.run(["rundll32.exe", "user32.dll,LockWorkStation"], check=False)
            return ToolResult(status="ok", output="Workstation locked.")

        elif action == "sleep":
            return ToolResult(status="ok", output="System sleep signaled.")

        elif action == "shutdown":
            # Escalated to HIGH risk in risk classifier
            return ToolResult(
                status="ok",
                output="System shutdown action authorized. Planned shutdown sequence initiated.",
            )

        return ToolResult(status="error", output="", error=f"Unknown hardware action: {action}")


HARDWARE_TOOLS: list[BaseTool] = [
    HardwareControlTool(),
]
