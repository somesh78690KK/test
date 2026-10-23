"""T.A.R.O. - PowerPoint presentation automation capability.

ARCHITECTURE reference: section 14.
RULES reference: section 3, 10.
TASKS: TASK-048.

Creates, edits, and reads PowerPoint presentations (.pptx) using python-pptx.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from capabilities.files.workspace import normalize_path
from core.log.setup import get_logger
from core.tools.base import BaseTool, RiskLevel, ToolCategory, ToolResult

logger = get_logger(__name__)


class PowerPointTool(BaseTool):
    """Creates or inspects PowerPoint (.pptx) presentations."""

    name = "powerpoint.manage"
    description = "Create or inspect PowerPoint presentations (.pptx) with slides, titles, and bullet points."
    category = ToolCategory.OFFICE
    risk = RiskLevel.LOW
    timeout_s = 20
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["create", "read", "add_slide"],
                "description": "Action to perform on presentation.",
            },
            "path": {"type": "string", "description": "Target .pptx file path."},
            "title": {"type": "string", "description": "Presentation or title slide heading."},
            "slides": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "content": {"type": "string"},
                    },
                    "required": ["title", "content"],
                },
                "description": "List of slide specifications.",
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
            import pptx

            deck_path = normalize_path(path_str)
            if deck_path.suffix.lower() != ".pptx":
                deck_path = deck_path.with_suffix(".pptx")

            deck_path.parent.mkdir(parents=True, exist_ok=True)

            if action == "create":
                prs = pptx.Presentation()
                title = kwargs.get("title", "")
                slides_data = kwargs.get("slides", [])

                # Add Title slide
                if title:
                    title_slide_layout = prs.slide_layouts[0]
                    slide = prs.slides.add_slide(title_slide_layout)
                    slide.shapes.title.text = title

                # Add content slides
                bullet_slide_layout = prs.slide_layouts[1]
                for s in slides_data:
                    slide = prs.slides.add_slide(bullet_slide_layout)
                    slide.shapes.title.text = s.get("title", "")
                    body = slide.shapes.placeholders[1]
                    body.text = s.get("content", "")

                prs.save(str(deck_path))
                total_slides = (1 if title else 0) + len(slides_data)
                return ToolResult(
                    status="ok",
                    output=f"Created presentation '{deck_path.name}' with {total_slides} slide(s) at '{deck_path}'.",
                )

            elif action == "read":
                if not deck_path.exists():
                    return ToolResult(status="error", output="", error=f"Deck not found: {deck_path}")

                prs = pptx.Presentation(str(deck_path))
                lines = [f"Presentation: {deck_path.name} ({len(prs.slides)} slides)"]
                for idx, slide in enumerate(prs.slides, 1):
                    titles = [shape.text for shape in slide.shapes if shape.has_text_frame]
                    lines.append(f"\n--- Slide {idx} ---")
                    lines.append("\n".join(titles))

                return ToolResult(status="ok", output="\n".join(lines))

            return ToolResult(status="error", output="", error=f"Unknown action: {action}")

        except Exception as e:
            logger.error("pptx_manage_error", error=str(e), path=path_str)
            return ToolResult(status="error", output="", error=f"PowerPoint operation failed: {e}")


POWERPOINT_TOOLS: list[BaseTool] = [
    PowerPointTool(),
]
