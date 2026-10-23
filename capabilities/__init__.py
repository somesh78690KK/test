"""T.A.R.O. - Capabilities registration.

Loads and registers all core capability tools into the ToolRegistry.
"""

from __future__ import annotations

from capabilities.coding.sandbox import CODING_TOOLS
from capabilities.files.operations import FILE_TOOLS
from capabilities.notes.notes import NOTES_TOOLS
from capabilities.office.excel import EXCEL_TOOLS
from capabilities.office.excel_advanced import EXCEL_ADVANCED_TOOLS
from capabilities.office.powerpoint import POWERPOINT_TOOLS
from capabilities.office.word import WORD_TOOLS
from capabilities.reminders.timers import TIMER_TOOLS
from capabilities.system.apps import APP_TOOLS
from capabilities.system.clipboard import CLIPBOARD_TOOLS
from capabilities.system.hardware import HARDWARE_TOOLS
from capabilities.system.input_control import INPUT_TOOLS
from capabilities.system.processes import PROCESS_TOOLS
from capabilities.system.stats import STATS_TOOLS
from capabilities.system.ui_automation import UI_AUTOMATION_TOOLS
from capabilities.system.ui_automation_advanced import UI_AUTOMATION_ADVANCED_TOOLS
from capabilities.system.app_intel import APP_INTEL_TOOLS
from capabilities.system.windows import WINDOW_TOOLS
from capabilities.system.system_advanced import SYSTEM_ADVANCED_TOOLS
from capabilities.system.whatsapp_automation import WHATSAPP_AUTOMATION_TOOLS
from capabilities.system.monitoring import MONITORING_TOOLS
from capabilities.memory.app_memory import APP_MEMORY_TOOLS
from capabilities.vision.capture import CAPTURE_TOOLS
from capabilities.vision.ocr import OCR_TOOLS
from capabilities.vision.vlm import VISION_TOOLS
from capabilities.vision.camera import CAMERA_TOOLS
from capabilities.web.fetch import WEB_FETCH_TOOLS
from capabilities.web.search import WEB_TOOLS
from capabilities.web.browser_automation import BROWSER_AUTOMATION_TOOLS
from core.log.setup import get_logger
from core.tools.base import BaseTool
from core.tools.registry import ToolRegistry

logger = get_logger(__name__)

ALL_CAPABILITY_TOOLS: list[BaseTool] = [
    *FILE_TOOLS,
    *CODING_TOOLS,
    *APP_TOOLS,
    *WINDOW_TOOLS,
    *PROCESS_TOOLS,
    *HARDWARE_TOOLS,
    *STATS_TOOLS,
    *CLIPBOARD_TOOLS,
    *INPUT_TOOLS,
    *UI_AUTOMATION_TOOLS,
    *APP_INTEL_TOOLS,
    *CAPTURE_TOOLS,
    *OCR_TOOLS,
    *VISION_TOOLS,
    *CAMERA_TOOLS,
    *WEB_TOOLS,
    *WEB_FETCH_TOOLS,
    *BROWSER_AUTOMATION_TOOLS,
    *TIMER_TOOLS,
    *NOTES_TOOLS,
    *EXCEL_TOOLS,
    *EXCEL_ADVANCED_TOOLS,
    *WORD_TOOLS,
    *POWERPOINT_TOOLS,
    *SYSTEM_ADVANCED_TOOLS,
    *WHATSAPP_AUTOMATION_TOOLS,
    *MONITORING_TOOLS,
    *APP_MEMORY_TOOLS,
]


def register_all_capabilities(registry: ToolRegistry) -> int:
    """Registers all built-in capability tools into the registry.

    Returns:
        Count of successfully registered tools.
    """
    count = 0
    for tool in ALL_CAPABILITY_TOOLS:
        try:
            if registry.get(tool.name) is None:
                registry.register(tool)
                count += 1
        except Exception as e:
            logger.error("capability_register_error", tool=tool.name, error=str(e))
    logger.info("all_capabilities_registered", count=count)
    return count
