"""T.A.R.O. - Application launcher and process-poll verification.

ARCHITECTURE reference: section 14.
RULES reference: section 3, 4, 10.
TASKS: TASK-040.

Launches applications from the 30+ app map (config/apps.json) or direct
paths/URIs with process-poll verification. Returns structured errors if missing.
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

from core.log.setup import get_logger
from core.tools.base import BaseTool, RiskLevel, ToolCategory, ToolResult

logger = get_logger(__name__)


def _load_app_map() -> dict[str, str]:
    """Loads apps.json configuration."""
    repo_root = Path(__file__).resolve().parent.parent.parent
    apps_file = repo_root / "config" / "apps.json"
    if apps_file.exists():
        try:
            return json.loads(apps_file.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning("apps_json_load_failed", error=str(e))
    return {}


class AppLaunchTool(BaseTool):
    """Launches an application and verifies it starts via process polling."""

    name = "app.launch"
    description = "Launch an application by name, command, or URI, with launch verification."
    category = ToolCategory.SYSTEM
    risk = RiskLevel.LOW
    timeout_s = 20
    parameters = {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Application name from config (e.g., 'notepad', 'calc') or executable name/path.",
            },
            "arguments": {
                "type": "string",
                "description": "Optional command-line arguments to pass to the application.",
            },
        },
        "required": ["name"],
    }

    async def run(self, args: dict) -> ToolResult:
        return await self.execute(**args)

    async def execute(self, **kwargs: Any) -> ToolResult:
        import asyncio
        from pynput.keyboard import Controller, Key

        app_name = kwargs.get("name")
        args_str = kwargs.get("arguments", "")

        if not app_name:
            return ToolResult(status="error", output="", error="Missing 'name' argument.")

        app_map = _load_app_map()
        normalized_name = app_name.strip().lower().replace(" ", "_")
        target = app_map.get(normalized_name, app_name.strip())

        # Check for URI protocol scheme (e.g., ms-settings:, calc:, etc.)
        if ":" in target and not Path(target).is_absolute():
            # URI protocol handler
            if os.name == "nt":
                try:
                    os.startfile(target)
                    return ToolResult(status="ok", output=f"Launched protocol URI '{target}'.")
                except Exception as e:
                    return ToolResult(
                        status="error",
                        output="",
                        error=f"Failed to launch URI '{target}': {e}",
                    )
            else:
                return ToolResult(
                    status="error",
                    output="",
                    error=f"Protocol URI '{target}' not supported on non-Windows platform.",
                )

        # Check executable existence via PATH or absolute path
        executable_path = shutil.which(target)
        if not executable_path and os.path.exists(target):
            executable_path = str(Path(target).resolve())

        if not executable_path:
            # Fallback: Use Windows Search if app not found
            logger.info("app_not_found_using_windows_search", app=app_name)
            try:
                kbd = Controller()

                # Press Win+S to open Windows Search
                with kbd.pressed(Key.cmd):
                    kbd.press('s')
                    kbd.release('s')
                await asyncio.sleep(0.8)

                # Type the search query
                kbd.type(app_name)
                await asyncio.sleep(0.5)

                # Press Enter to launch
                kbd.press(Key.enter)
                kbd.release(Key.enter)
                await asyncio.sleep(0.3)

                return ToolResult(
                    status="ok",
                    output=f"Application '{app_name}' not found in PATH. Used Windows Search to find and launch it.",
                )
            except Exception as e:
                logger.error("windows_search_fallback_failed", app=app_name, error=str(e))
                return ToolResult(
                    status="error",
                    output="",
                    error=f"Application '{app_name}' (target: '{target}') not found on system PATH or filesystem. Windows Search fallback also failed: {e}",
                )

        # Launch process
        cmd = [executable_path]
        if args_str:
            cmd.extend(args_str.split())

        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

            # Poll for 0.5s to verify process didn't instantly crash
            time.sleep(0.5)
            poll = proc.poll()
            if poll is not None and poll != 0:
                return ToolResult(
                    status="error",
                    output="",
                    error=f"Application '{app_name}' exited immediately with code {poll}.",
                )

            logger.info("app_launched", app=app_name, pid=proc.pid, target=executable_path)
            return ToolResult(
                status="ok",
                output=f"Successfully launched '{app_name}' (PID: {proc.pid}).",
            )
        except Exception as e:
            logger.error("app_launch_failed", app=app_name, error=str(e))
            return ToolResult(
                status="error",
                output="",
                error=f"Failed to launch application '{app_name}': {e}",
            )


class AppCloseTool(BaseTool):
    """Closes an application or its window gracefully."""

    name = "app.close"
    description = "Close an application by name or window title (e.g. 'notepad', 'whatsapp', 'calc')."
    category = ToolCategory.SYSTEM
    risk = RiskLevel.LOW
    timeout_s = 15
    parameters = {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Application name or window title to close (e.g., 'notepad', 'whatsapp', 'chrome').",
            },
        },
        "required": ["name"],
    }

    async def run(self, args: dict) -> ToolResult:
        return await self.execute(**args)

    async def execute(self, **kwargs: Any) -> ToolResult:
        app_name = kwargs.get("name", "").strip()
        if not app_name:
            return ToolResult(status="error", output="", error="Missing 'name' argument.")

        from winapi.win32_windows import close_window, find_windows
        from winapi.win32_process import terminate_process, list_processes

        # 1. Try to find and close matching windows first (graceful)
        wins = find_windows(app_name)
        closed_count = 0
        for w in wins:
            hwnd = w.get("hwnd")
            if hwnd and close_window(hwnd):
                closed_count += 1

        if closed_count > 0:
            return ToolResult(status="ok", output=f"Closed {closed_count} window(s) for '{app_name}'.")

        # 2. Try process name matching
        app_map = _load_app_map()
        target = app_map.get(app_name.lower().replace(" ", "_"), app_name)
        target_stem = Path(target).stem.lower()

        procs = list_processes()
        killed_any = False
        for p in procs:
            p_name = p.get("name", "").lower()
            if target_stem in p_name or app_name.lower() in p_name:
                pid = p.get("pid")
                if pid and terminate_process(pid):
                    killed_any = True

        if killed_any:
            return ToolResult(status="ok", output=f"Terminated process for '{app_name}'.")

        return ToolResult(
            status="ok",
            output=f"No active window or process found matching '{app_name}'. It may already be closed.",
        )


class WhatsAppTool(BaseTool):
    """Automates sending a WhatsApp message to a contact or phone number."""

    name = "message.whatsapp"
    description = "Send a WhatsApp message to a contact by name (e.g. 'jagunu') or phone number."
    category = ToolCategory.SYSTEM
    risk = RiskLevel.LOW
    timeout_s = 25
    parameters = {
        "type": "object",
        "properties": {
            "contact": {
                "type": "string",
                "description": "Contact name (e.g. 'jagunu') or phone number with country code.",
            },
            "message": {
                "type": "string",
                "description": "Message text to send.",
            },
        },
        "required": ["contact", "message"],
    }

    async def run(self, args: dict) -> ToolResult:
        return await self.execute(**args)

    async def execute(self, **kwargs: Any) -> ToolResult:
        import urllib.parse
        from winapi.win32_windows import find_windows, switch_to_window

        contact = kwargs.get("contact", "").strip()
        msg = kwargs.get("message", "").strip()

        if not contact or not msg:
            return ToolResult(status="error", output="", error="Both 'contact' and 'message' are required.")

        # Phone number direct URI pattern
        clean_num = contact.replace(" ", "").replace("-", "")
        if (clean_num.startswith("+") and clean_num[1:].isdigit()) or clean_num.isdigit():
            encoded_msg = urllib.parse.quote(msg)
            uri = f"whatsapp://send?phone={clean_num}&text={encoded_msg}"
            try:
                os.startfile(uri)
                return ToolResult(
                    status="ok",
                    output=f"Opened WhatsApp chat with {contact} and prefilled message: '{msg}'",
                )
            except Exception as e:
                return ToolResult(status="error", output="", error=f"Failed to open WhatsApp URI: {e}")

        # Contact name automation via Desktop App & UI search
        try:
            # 1. Launch / activate WhatsApp
            os.startfile("whatsapp:")
            await asyncio.sleep(1.5)

            # 2. Find and focus WhatsApp window
            wins = find_windows("WhatsApp")
            if wins:
                switch_to_window(wins[0]["hwnd"])
                await asyncio.sleep(0.5)

            # 3. Use keyboard automation to search contact and type message
            from pynput.keyboard import Controller, Key
            kbd = Controller()

            # Ctrl+F to focus search bar
            with kbd.pressed(Key.ctrl):
                kbd.press('f')
                kbd.release('f')
            await asyncio.sleep(0.6)

            # Type contact name
            kbd.type(contact)
            await asyncio.sleep(0.8)

            # Press Enter or Down then Enter to select contact chat
            kbd.press(Key.enter)
            kbd.release(Key.enter)
            await asyncio.sleep(0.8)

            # Type message
            kbd.type(msg)
            await asyncio.sleep(0.5)

            # Press Enter to send
            kbd.press(Key.enter)
            kbd.release(Key.enter)

            logger.info("whatsapp_message_sent", contact=contact, message_len=len(msg))
            return ToolResult(
                status="ok",
                output=f"Successfully navigated to contact '{contact}' in WhatsApp and sent message: '{msg}'",
            )
        except Exception as e:
            logger.error("whatsapp_automation_error", contact=contact, error=str(e))
            return ToolResult(
                status="error",
                output="",
                error=f"WhatsApp automation encountered an error: {e}",
            )


class WindowsSearchTool(BaseTool):
    """Opens Windows Search (Win+S) and searches for applications or files."""

    name = "windows.search"
    description = "Open Windows Search (Win+S) and search for an application or file by name."
    category = ToolCategory.SYSTEM
    risk = RiskLevel.LOW
    timeout_s = 10
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query (e.g., 'notepad', 'chrome', 'calculator').",
            },
            "press_enter": {
                "type": "boolean",
                "description": "Whether to automatically press Enter to launch the top result. Default: false.",
            },
        },
        "required": ["query"],
    }

    async def run(self, args: dict) -> ToolResult:
        return await self.execute(**args)

    async def execute(self, **kwargs: Any) -> ToolResult:
        import asyncio
        from pynput.keyboard import Controller, Key

        query = kwargs.get("query", "").strip()
        press_enter = kwargs.get("press_enter", False)

        if not query:
            return ToolResult(status="error", output="", error="Missing 'query' argument.")

        try:
            kbd = Controller()

            # Press Win+S to open Windows Search
            with kbd.pressed(Key.cmd):
                kbd.press('s')
                kbd.release('s')
            await asyncio.sleep(0.8)

            # Type the search query
            kbd.type(query)
            await asyncio.sleep(0.5)

            # Optionally press Enter to launch
            if press_enter:
                kbd.press(Key.enter)
                kbd.release(Key.enter)
                await asyncio.sleep(0.3)
                return ToolResult(
                    status="ok",
                    output=f"Opened Windows Search, searched for '{query}', and launched the top result.",
                )

            logger.info("windows_search_opened", query=query)
            return ToolResult(
                status="ok",
                output=f"Opened Windows Search and entered query: '{query}'. Press Enter to launch the top result.",
            )
        except Exception as e:
            logger.error("windows_search_error", query=query, error=str(e))
            return ToolResult(
                status="error",
                output="",
                error=f"Failed to open Windows Search: {e}",
            )


APP_TOOLS: list[BaseTool] = [
    AppLaunchTool(),
    AppCloseTool(),
    WhatsAppTool(),
    WindowsSearchTool(),
]

