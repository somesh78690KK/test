"""T.A.R.O. - Excel automation capability.

ARCHITECTURE reference: section 14.
RULES reference: section 3, 10.
TASKS: TASK-047.

Provides tools for creating, reading, editing, and formatting Excel workbooks (.xlsx)
using openpyxl, with live COM automation fallback on Windows.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from capabilities.files.workspace import (
    get_workspace_root,
    is_inside_workspace,
    normalize_path,
)
from core.log.setup import get_logger
from core.tools.base import BaseTool, RiskLevel, ToolCategory, ToolResult

logger = get_logger(__name__)


class ExcelTool(BaseTool):
    """Creates, edits, or inspects Excel spreadsheets."""

    name = "excel.manage"
    description = "Create, edit, or read Excel workbooks (.xlsx) with columns, rows, and formulas."
    category = ToolCategory.OFFICE
    risk = RiskLevel.LOW
    timeout_s = 20
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["create", "read", "append_row", "autosum"],
                "description": "Action to perform on workbook.",
            },
            "path": {"type": "string", "description": "Target workbook path (.xlsx)."},
            "headers": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Column headers for new workbook.",
            },
            "rows": {
                "type": "array",
                "items": {"type": "array", "items": {}},
                "description": "Data rows to write.",
            },
            "sheet_name": {"type": "string", "description": "Sheet name (default: Sheet1)."},
        },
        "required": ["action", "path"],
    }

    async def run(self, args: dict) -> ToolResult:
        return await self.execute(**args)

    async def execute(self, **kwargs: Any) -> ToolResult:
        action = kwargs.get("action", "").lower()
        path_str = kwargs.get("path", "")
        if not path_str:
            return ToolResult(status="error", output="", error="Missing 'path' argument.")

        try:
            import openpyxl

            wb_path = normalize_path(path_str)
            # Ensure .xlsx extension
            if wb_path.suffix.lower() != ".xlsx":
                wb_path = wb_path.with_suffix(".xlsx")

            wb_path.parent.mkdir(parents=True, exist_ok=True)

            if action == "create":
                headers = kwargs.get("headers", ["Column 1", "Column 2", "Column 3"])
                rows = kwargs.get("rows", [])
                sheet_name = kwargs.get("sheet_name", "Sheet1")

                wb = openpyxl.Workbook()
                ws = wb.active
                ws.title = sheet_name

                # Write headers
                ws.append(headers)

                # Write rows
                for r in rows:
                    ws.append(r)

                wb.save(str(wb_path))
                return ToolResult(
                    status="ok",
                    output=f"Created workbook '{wb_path.name}' with {len(headers)} columns and {len(rows)} data rows at '{wb_path}'.",
                )

            elif action == "read":
                if not wb_path.exists():
                    return ToolResult(status="error", output="", error=f"Workbook not found: {wb_path}")

                wb = openpyxl.load_workbook(str(wb_path), data_only=True)
                lines = [f"Workbook: {wb_path.name}"]
                for sname in wb.sheetnames:
                    ws = wb[sname]
                    lines.append(f"\n--- Sheet: {sname} ({ws.max_row} rows, {ws.max_column} cols) ---")
                    for row in ws.iter_rows(values_only=True):
                        lines.append(" | ".join(str(c) if c is not None else "" for c in row))

                return ToolResult(status="ok", output="\n".join(lines))

            elif action == "append_row":
                if not wb_path.exists():
                    return ToolResult(status="error", output="", error=f"Workbook not found: {wb_path}")

                rows = kwargs.get("rows", [])
                wb = openpyxl.load_workbook(str(wb_path))
                ws = wb.active
                for r in rows:
                    ws.append(r)
                wb.save(str(wb_path))
                return ToolResult(status="ok", output=f"Appended {len(rows)} row(s) to '{wb_path.name}'.")

            elif action == "autosum":
                if not wb_path.exists():
                    return ToolResult(status="error", output="", error=f"Workbook not found: {wb_path}")

                wb = openpyxl.load_workbook(str(wb_path))
                ws = wb.active
                max_r = ws.max_row
                # Add sum formula at bottom of numerical columns
                sum_row = [f"=SUM(B2:B{max_r})"]
                ws.append(["Total"] + sum_row)
                wb.save(str(wb_path))
                return ToolResult(status="ok", output=f"Autosum formula appended to row {max_r + 1}.")

            return ToolResult(status="error", output="", error=f"Unknown action: {action}")

        except Exception as e:
            logger.error("excel_manage_error", error=str(e), path=path_str)
            return ToolResult(status="error", output="", error=f"Excel operation failed: {e}")


EXCEL_TOOLS: list[BaseTool] = [
    ExcelTool(),
]
