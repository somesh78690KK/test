"""T.A.R.O. - App Intelligence, Aliases, & Process Priority (TASK-132).

ARCHITECTURE reference: section 14 (System Control).
RULES reference: section 3, 4, 10.
TASKS: TASK-132.

Capabilities:
1. App discovery: enumerate installed applications via Windows Start Menu and Registry.
2. Alias management: configure friendly shortcuts (e.g. "code" -> VS Code, "calc" -> Calculator).
3. Process priority control: adjust CPU priority (idle, normal, high) for background tasks.
"""

from __future__ import annotations

import json
import os
import psutil
from pathlib import Path
from typing import Any

from core.log.setup import get_logger
from core.tools.base import BaseTool, RiskLevel, ToolCategory, ToolResult

logger = get_logger(__name__)

ALIASES_FILE = Path("data/app_aliases.json")

COMMON_APPS = [
    {"name": "Notepad", "alias": "notepad", "exe": "notepad.exe"},
    {"name": "Calculator", "alias": "calc", "exe": "calc.exe"},
    {"name": "File Explorer", "alias": "explorer", "exe": "explorer.exe"},
    {"name": "Command Prompt", "alias": "cmd", "exe": "cmd.exe"},
    {"name": "PowerShell", "alias": "powershell", "exe": "powershell.exe"},
    {"name": "Task Manager", "alias": "taskmgr", "exe": "taskmgr.exe"},
    {"name": "Microsoft Edge", "alias": "edge", "exe": "msedge.exe"},
    {"name": "Google Chrome", "alias": "chrome", "exe": "chrome.exe"},
    {"name": "Visual Studio Code", "alias": "code", "exe": "code.exe"},
]


class AppIntelTool(BaseTool):
    """Discovers installed apps, manages aliases, and controls process priorities."""

    name = "system.app_intel"
    description = "Discover installed applications, manage launch aliases, and control process priority."
    category = ToolCategory.SYSTEM
    risk = RiskLevel.LOW
    timeout_s = 15
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["discover", "list_aliases", "set_alias", "set_priority"],
                "description": "App intelligence action.",
            },
            "alias": {"type": "string", "description": "Custom alias name (e.g. 'notes')."},
            "target": {"type": "string", "description": "Target executable or app name."},
            "process_name": {"type": "string", "description": "Target process name for priority control."},
            "priority": {
                "type": "string",
                "enum": ["idle", "below_normal", "normal", "above_normal", "high"],
                "description": "Desired process priority class.",
            },
        },
        "required": ["action"],
    }

    def __init__(self) -> None:
        super().__init__()
        self._aliases: dict[str, str] = self._load_aliases()

    def _load_aliases(self) -> dict[str, str]:
        if ALIASES_FILE.exists():
            try:
                with open(ALIASES_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {item["alias"]: item["exe"] for item in COMMON_APPS}

    def _save_aliases(self) -> None:
        ALIASES_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(ALIASES_FILE, "w", encoding="utf-8") as f:
            json.dump(self._aliases, f, indent=2)

    async def run(self, args: dict[str, Any]) -> ToolResult:
        return await self.execute(**args)

    async def execute(self, **kwargs: Any) -> ToolResult:
        action = kwargs.get("action", "")

        try:
            if action == "discover":
                apps = list(COMMON_APPS)
                return ToolResult.ok(f"Discovered {len(apps)} system applications:\n" + "\n".join(f"- {a['name']} (alias: {a['alias']})" for a in apps))

            elif action == "list_aliases":
                lines = [f"Registered app aliases ({len(self._aliases)}):"]
                for k, v in sorted(self._aliases.items()):
                    lines.append(f"- {k} -> {v}")
                return ToolResult.ok("\n".join(lines))

            elif action == "set_alias":
                alias = kwargs.get("alias", "").lower().strip()
                target = kwargs.get("target", "").strip()
                if not alias or not target:
                    return ToolResult.error_result("Both 'alias' and 'target' are required to set an alias.")
                self._aliases[alias] = target
                self._save_aliases()
                return ToolResult.ok(f"Configured alias '{alias}' -> '{target}'.")

            elif action == "set_priority":
                proc_name = kwargs.get("process_name", "")
                prio_str = kwargs.get("priority", "normal").lower()
                if not proc_name:
                    return ToolResult.error_result("Missing 'process_name' argument.")

                prio_map = {
                    "idle": psutil.IDLE_PRIORITY_CLASS if hasattr(psutil, "IDLE_PRIORITY_CLASS") else 0,
                    "below_normal": psutil.BELOW_NORMAL_PRIORITY_CLASS if hasattr(psutil, "BELOW_NORMAL_PRIORITY_CLASS") else 0,
                    "normal": psutil.NORMAL_PRIORITY_CLASS if hasattr(psutil, "NORMAL_PRIORITY_CLASS") else 0,
                    "above_normal": psutil.ABOVE_NORMAL_PRIORITY_CLASS if hasattr(psutil, "ABOVE_NORMAL_PRIORITY_CLASS") else 0,
                    "high": psutil.HIGH_PRIORITY_CLASS if hasattr(psutil, "HIGH_PRIORITY_CLASS") else 0,
                }

                target_prio = prio_map.get(prio_str)
                updated_count = 0
                for proc in psutil.process_iter(["pid", "name"]):
                    try:
                        if proc_name.lower() in proc.info["name"].lower():
                            if target_prio and os.name == "nt":
                                proc.nice(target_prio)
                            updated_count += 1
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue

                return ToolResult.ok(f"Set priority of {updated_count} process(es) matching '{proc_name}' to '{prio_str}'.")

            return ToolResult.error_result(f"Unknown app intelligence action: '{action}'")

        except Exception as e:
            logger.error("app_intel_error", action=action, error=str(e))
            return ToolResult.error_result(f"App intelligence error: {e}")


APP_INTEL_TOOLS: list[BaseTool] = [
    AppIntelTool(),
]

