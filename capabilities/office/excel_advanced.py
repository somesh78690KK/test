"""T.A.R.O. - Advanced Excel Automation Skills.

Provides tools for Excel operations like editing cells, formatting, and navigation.
"""

from __future__ import annotations

from typing import Any

from core.log.setup import get_logger
from core.tools.base import BaseTool, RiskLevel, ToolCategory, ToolResult

logger = get_logger(__name__)


class ExcelEditCellTool(BaseTool):
    """Edit a specific cell in Excel."""

    name = "excel.edit_cell"
    description = "Edit a specific cell in Excel by providing the cell address and new value."
    category = ToolCategory.OFFICE
    risk = RiskLevel.LOW
    timeout_s = 10
    parameters = {
        "type": "object",
        "properties": {
            "cell": {
                "type": "string",
                "description": "Cell address (e.g., 'A1', 'B5').",
            },
            "value": {
                "type": "string",
                "description": "New value to set in the cell.",
            },
        },
        "required": ["cell", "value"],
    }

    async def run(self, args: dict) -> ToolResult:
        return await self.execute(**args)

    async def execute(self, **kwargs: Any) -> ToolResult:
        cell = kwargs.get("cell", "").strip()
        value = kwargs.get("value", "").strip()
        
        if not cell:
            return ToolResult(status="error", output="", error="Missing 'cell' argument.")
        
        try:
            from win32com.client import Dispatch
            xl = Dispatch("Excel.Application")
            xl.Visible = True
            
            sheet = xl.ActiveSheet
            sheet.Range(cell).Value = value
            
            return ToolResult(status="ok", output=f"Set cell {cell} to '{value}'.")
        except Exception as e:
            return ToolResult(status="error", output="", error=f"Failed to edit cell: {e}")


class ExcelAutosumTool(BaseTool):
    """Apply autosum to a range."""

    name = "excel.autosum"
    description = "Apply the SUM formula to a range of cells in Excel."
    category = ToolCategory.OFFICE
    risk = RiskLevel.LOW
    timeout_s = 10
    parameters = {
        "type": "object",
        "properties": {
            "range": {
                "type": "string",
                "description": "Cell range to sum (e.g., 'A1:A10').",
            },
        },
        "required": ["range"],
    }

    async def run(self, args: dict) -> ToolResult:
        return await self.execute(**args)

    async def execute(self, **kwargs: Any) -> ToolResult:
        range_str = kwargs.get("range", "").strip()
        
        if not range_str:
            return ToolResult(status="error", output="", error="Missing 'range' argument.")
        
        try:
            from win32com.client import Dispatch
            xl = Dispatch("Excel.Application")
            xl.Visible = True
            
            sheet = xl.ActiveSheet
            # Find the cell below the range for the sum
            sheet.Range(range_str).End(-4162).Offset(1, 0).Formula = f"=SUM({range_str})"
            
            return ToolResult(status="ok", output=f"Applied SUM formula to range {range_str}.")
        except Exception as e:
            return ToolResult(status="error", output="", error=f"Failed to apply autosum: {e}")


class ExcelSelectDataRangeTool(BaseTool):
    """Select a data range in Excel."""

    name = "excel.select_data_range"
    description = "Select a specific range of cells in Excel."
    category = ToolCategory.OFFICE
    risk = RiskLevel.LOW
    timeout_s = 10
    parameters = {
        "type": "object",
        "properties": {
            "range": {
                "type": "string",
                "description": "Cell range to select (e.g., 'A1:D10').",
            },
        },
        "required": ["range"],
    }

    async def run(self, args: dict) -> ToolResult:
        return await self.execute(**args)

    async def execute(self, **kwargs: Any) -> ToolResult:
        range_str = kwargs.get("range", "").strip()
        
        if not range_str:
            return ToolResult(status="error", output="", error="Missing 'range' argument.")
        
        try:
            from win32com.client import Dispatch
            xl = Dispatch("Excel.Application")
            xl.Visible = True
            
            sheet = xl.ActiveSheet
            sheet.Range(range_str).Select()
            
            return ToolResult(status="ok", output=f"Selected range {range_str}.")
        except Exception as e:
            return ToolResult(status="error", output="", error=f"Failed to select range: {e}")


EXCEL_ADVANCED_TOOLS: list[BaseTool] = [
    ExcelEditCellTool(),
    ExcelAutosumTool(),
    ExcelSelectDataRangeTool(),
]
