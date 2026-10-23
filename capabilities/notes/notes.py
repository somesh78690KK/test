"""T.A.R.O. - Notes capability (dual storage in ChromaDB and Markdown).

ARCHITECTURE reference: section 12, 14.
RULES reference: section 3, 10.
TASKS: TASK-053.

Stores notes both as local markdown files in `data/notes/` and as semantic
embeddings in ChromaDB, enabling full-text and semantic search.
"""

from __future__ import annotations

import datetime
import re
from pathlib import Path
from typing import Any

from core.log.setup import get_logger
from core.memory.chroma_store import get_chroma_store
from core.tools.base import BaseTool, RiskLevel, ToolCategory, ToolResult

logger = get_logger(__name__)


def _get_notes_dir() -> Path:
    repo_root = Path(__file__).resolve().parent.parent.parent
    notes_dir = repo_root / "data" / "notes"
    notes_dir.mkdir(parents=True, exist_ok=True)
    return notes_dir


def _slugify(text: str) -> str:
    slug = re.sub(r"[^\w\- ]", "", text).strip().replace(" ", "_").lower()
    return slug[:50] or "note"


class NoteSaveTool(BaseTool):
    """Saves a note as markdown and indexes it in ChromaDB."""

    name = "notes.save"
    description = "Save a note as a markdown file and index it for semantic retrieval."
    category = ToolCategory.NOTES
    risk = RiskLevel.LOW
    timeout_s = 15
    parameters = {
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "Title of the note."},
            "content": {"type": "string", "description": "Markdown body content of the note."},
            "tags": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional tags for categorization.",
            },
        },
        "required": ["title", "content"],
    }

    async def run(self, args: dict) -> ToolResult:
        return await self.execute(**args)

    async def execute(self, **kwargs: Any) -> ToolResult:
        title = kwargs.get("title", "").strip()
        content = kwargs.get("content", "").strip()
        tags = kwargs.get("tags", [])

        if not title or not content:
            return ToolResult(status="error", output="", error="Both 'title' and 'content' are required.")

        try:
            # 1. Save Markdown file
            notes_dir = _get_notes_dir()
            ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d_%H%M%S")
            filename = f"{_slugify(title)}_{ts}.md"
            note_file = notes_dir / filename

            frontmatter = f"---\ntitle: {title}\ntags: {tags}\ncreated: {ts}\n---\n\n"
            note_file.write_text(frontmatter + content, encoding="utf-8")

            # 2. Add to ChromaDB notes collection
            chroma = get_chroma_store()
            doc_text = f"Title: {title}\nTags: {', '.join(tags)}\n\n{content}"
            rec_id = chroma.add(
                collection_name="notes",
                text=doc_text,
                source="user_notes",
                metadata={"title": title, "file": str(note_file), "tags": ",".join(tags)},
            )

            logger.info("note_saved", title=title, file=str(note_file), rec_id=rec_id)
            return ToolResult(
                status="ok",
                output=f"Note '{title}' saved successfully to '{note_file.name}' and indexed in memory.",
            )

        except Exception as e:
            logger.error("note_save_error", title=title, error=str(e))
            return ToolResult(status="error", output="", error=f"Failed to save note: {e}")


class NoteSearchTool(BaseTool):
    """Searches notes by semantic similarity in ChromaDB."""

    name = "notes.search"
    description = "Search saved notes using semantic similarity."
    category = ToolCategory.NOTES
    risk = RiskLevel.SAFE
    timeout_s = 10
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query."},
            "max_results": {"type": "integer", "description": "Maximum notes to return (default 4)."},
        },
        "required": ["query"],
    }

    async def run(self, args: dict) -> ToolResult:
        return await self.execute(**args)

    async def execute(self, **kwargs: Any) -> ToolResult:
        query = kwargs.get("query", "").strip()
        max_results = kwargs.get("max_results", 4)

        if not query:
            return ToolResult(status="error", output="", error="Missing 'query' argument.")

        try:
            chroma = get_chroma_store()
            results = chroma.query("notes", query_text=query, n_results=max_results, min_similarity=0.1)

            if not results:
                # Fallback to text matching in files if chroma has no matches
                notes_dir = _get_notes_dir()
                matched_files = []
                for p in notes_dir.glob("*.md"):
                    txt = p.read_text(encoding="utf-8", errors="ignore")
                    if query.lower() in txt.lower():
                        matched_files.append((p.name, txt[:200]))

                if not matched_files:
                    return ToolResult(status="ok", output=f"No notes found matching '{query}'.")

                lines = [f"Found {len(matched_files)} notes matching '{query}' (keyword fallback):"]
                for fname, snippet in matched_files:
                    lines.append(f"- {fname}: {snippet}...")
                return ToolResult(status="ok", output="\n".join(lines))

            lines = [f"Found {len(results)} notes semantically matching '{query}':"]
            for r in results:
                title = r.metadata.get("title", "Untitled")
                fpath = r.metadata.get("file", "")
                fname = Path(fpath).name if fpath else "note"
                lines.append(f"- [{title}] (similarity: {r.similarity:.2f}, file: {fname})\n  {r.text[:250]}...")

            return ToolResult(status="ok", output="\n".join(lines))

        except Exception as e:
            logger.error("note_search_error", query=query, error=str(e))
            return ToolResult(status="error", output="", error=f"Failed to search notes: {e}")


NOTES_TOOLS: list[BaseTool] = [
    NoteSaveTool(),
    NoteSearchTool(),
]
