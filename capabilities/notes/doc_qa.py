"""T.A.R.O. - Local Document Q&A with Source Citation (TASK-145).

ARCHITECTURE reference: section 14 (Knowledge & Notes), section 26.
RULES reference: section 1 (Local First), section 4.
TASKS: TASK-145.

Capabilities:
- Indexes local documents (.txt, .md, .pdf) page by page.
- Extracts chunks with exact file path and page/section metadata.
- Answers queries by retrieving relevant chunks and strictly citing the source file and page.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.log.setup import get_logger
from core.tools.base import BaseTool, RiskLevel, ToolCategory, ToolResult

logger = get_logger(__name__)


@dataclass
class DocumentChunk:
    file_path: str
    file_name: str
    page: int
    text: str


class DocumentIndex:
    """Local offline document index with page citation support."""

    def __init__(self) -> None:
        self.chunks: list[DocumentChunk] = []

    def index_document(self, path: str | Path, content_by_page: list[str] | None = None) -> int:
        """Indexes a document, storing text page by page."""
        p = Path(path).resolve()
        file_name = p.name

        if content_by_page is not None:
            # Explicit pages provided (e.g. from PDF parser or test)
            for page_num, page_text in enumerate(content_by_page, 1):
                self.chunks.append(
                    DocumentChunk(
                        file_path=str(p),
                        file_name=file_name,
                        page=page_num,
                        text=page_text,
                    )
                )
            return len(content_by_page)

        # Read local file
        if not p.exists():
            return 0

        # Text / Markdown fallback chunking
        try:
            with open(p, "r", encoding="utf-8", errors="replace") as f:
                full_text = f.read()

            # Split by markdown headers or form-feeds or default ~1000 char pages
            raw_pages = full_text.split("\f")
            if len(raw_pages) == 1:
                # Approximate 1000 chars per page
                chars_per_page = 1000
                raw_pages = [
                    full_text[i : i + chars_per_page]
                    for i in range(0, len(full_text), chars_per_page)
                ] or [""]

            for page_num, page_text in enumerate(raw_pages, 1):
                self.chunks.append(
                    DocumentChunk(
                        file_path=str(p),
                        file_name=file_name,
                        page=page_num,
                        text=page_text.strip(),
                    )
                )
            return len(raw_pages)

        except Exception as e:
            logger.error("doc_index_error", file=str(p), error=str(e))
            return 0

    def query(self, query_text: str, top_k: int = 3) -> list[dict[str, Any]]:
        """Finds matching document chunks and formats citations."""
        terms = [t.lower() for t in query_text.split() if len(t) > 2]
        scored_chunks: list[tuple[int, DocumentChunk]] = []

        for chunk in self.chunks:
            chunk_lower = chunk.text.lower()
            score = sum(1 for term in terms if term in chunk_lower)
            if score > 0:
                scored_chunks.append((score, chunk))

        scored_chunks.sort(key=lambda x: x[0], reverse=True)
        top = scored_chunks[:top_k]

        results = []
        for score, ch in top:
            results.append({
                "file_name": ch.file_name,
                "file_path": ch.file_path,
                "page": ch.page,
                "citation": f"[Source: {ch.file_name}, Page {ch.page}]",
                "text": ch.text,
            })
        return results


class DocumentQATool(BaseTool):
    """Answers user queries by querying indexed documents and citing file and page."""

    name = "notes.doc_qa"
    description = (
        "Search indexed local documents and answer questions with exact file and page citations."
    )
    category = ToolCategory.NOTES
    risk = RiskLevel.LOW
    timeout_s = 20
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["index", "query"],
                "description": "Action: 'index' a document or 'query' indexed content.",
            },
            "path": {"type": "string", "description": "Document path to index."},
            "query": {"type": "string", "description": "Question or search query."},
        },
        "required": ["action"],
    }

    def __init__(self, doc_index: DocumentIndex | None = None) -> None:
        super().__init__()
        self.doc_index = doc_index or DocumentIndex()

    async def run(self, args: dict[str, Any]) -> ToolResult:
        return await self.execute(**args)

    async def execute(self, **kwargs: Any) -> ToolResult:
        action = kwargs.get("action", "query")

        if action == "index":
            path = kwargs.get("path", "")
            if not path:
                return ToolResult.error_result("Argument 'path' is required for indexing.")
            pages_count = self.doc_index.index_document(path)
            return ToolResult.ok(f"Indexed document '{path}' ({pages_count} page(s)).")

        elif action == "query":
            q = kwargs.get("query", "")
            if not q:
                return ToolResult.error_result("Argument 'query' is required.")

            matches = self.doc_index.query(q)
            if not matches:
                return ToolResult.ok(f"No relevant excerpts found for query: '{q}'.")

            lines = ["Found the following matching excerpts:"]
            for m in matches:
                lines.append(f"\n{m['citation']}\n\"{m['text']}\"")

            return ToolResult.ok("\n".join(lines), data=matches)

        return ToolResult.error_result(f"Unknown doc_qa action: '{action}'")
