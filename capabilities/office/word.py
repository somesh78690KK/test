"""T.A.R.O. - Word document automation capability.

ARCHITECTURE reference: section 14.
RULES reference: section 3, 10.
TASKS: TASK-048.

Creates, reads, and formats Word documents (.docx) using python-docx.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from capabilities.files.workspace import normalize_path
from core.log.setup import get_logger
from core.tools.base import BaseTool, RiskLevel, ToolCategory, ToolResult

logger = get_logger(__name__)


class WordTool(BaseTool):
    """Creates or modifies Word (.docx) documents."""

    name = "word.manage"
    description = "Create or inspect Word documents (.docx) with headings, paragraphs, and styling."
    category = ToolCategory.OFFICE
    risk = RiskLevel.LOW
    timeout_s = 20
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["create", "read", "append_paragraph"],
                "description": "Action to perform on document.",
            },
            "path": {"type": "string", "description": "Target .docx file path."},
            "title": {"type": "string", "description": "Document title / heading."},
            "paragraphs": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Paragraph texts to include.",
            },
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
            import docx

            doc_path = normalize_path(path_str)
            if doc_path.suffix.lower() != ".docx":
                doc_path = doc_path.with_suffix(".docx")

            doc_path.parent.mkdir(parents=True, exist_ok=True)

            if action == "create":
                title = kwargs.get("title", "")
                paragraphs = kwargs.get("paragraphs", [])

                doc = docx.Document()
                if title:
                    doc.add_heading(title, level=0)
                for p_text in paragraphs:
                    doc.add_paragraph(p_text)

                doc.save(str(doc_path))
                return ToolResult(
                    status="ok",
                    output=f"Created Word document '{doc_path.name}' with {len(paragraphs)} paragraph(s) at '{doc_path}'.",
                )

            elif action == "read":
                if not doc_path.exists():
                    return ToolResult(status="error", output="", error=f"Document not found: {doc_path}")

                doc = docx.Document(str(doc_path))
                lines = [f"Document: {doc_path.name}"]
                for p in doc.paragraphs:
                    if p.text.strip():
                        lines.append(p.text)

                return ToolResult(status="ok", output="\n\n".join(lines))

            elif action == "append_paragraph":
                if not doc_path.exists():
                    doc = docx.Document()
                else:
                    doc = docx.Document(str(doc_path))

                paragraphs = kwargs.get("paragraphs", [])
                for p_text in paragraphs:
                    doc.add_paragraph(p_text)
                doc.save(str(doc_path))
                return ToolResult(status="ok", output=f"Appended {len(paragraphs)} paragraph(s) to '{doc_path.name}'.")

            return ToolResult(status="error", output="", error=f"Unknown action: {action}")

        except Exception as e:
            logger.error("word_manage_error", error=str(e), path=path_str)
            return ToolResult(status="error", output="", error=f"Word operation failed: {e}")


WORD_TOOLS: list[BaseTool] = [
    WordTool(),
]
