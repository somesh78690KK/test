"""T.A.R.O. - Tool discovery and search meta-tool (TASK-110).

ARCHITECTURE reference: section 17.
RULES reference: section 3, 10.
TASKS: TASK-110.

Maintains tool search index to allow dynamic tool discovery.
When 100+ tools are registered, sending all schemas blows the 32,768 token budget.
The `find_tools` meta-tool queries the index and returns only the matching tools.

Acceptance (TASK-110): Query "rename photos" returns the matching tool;
context stays under budget with 100 tools registered.
"""

from __future__ import annotations

import re
from typing import Any

from core.log.setup import get_logger
from core.tools.base import BaseTool, RiskLevel, ToolCategory, ToolResult

logger = get_logger(__name__)


class ToolDiscoveryIndex:
    """Keyword and semantic search index over registered tools."""

    def __init__(self) -> None:
        self._tools: dict[str, dict[str, Any]] = {}

    def register_tool(self, tool_name: str, description: str, category: str, tags: list[str] | None = None) -> None:
        """Add a tool to the discovery catalog."""
        self._tools[tool_name] = {
            "name": tool_name,
            "description": description,
            "category": category,
            "tags": tags or [],
            "search_blob": f"{tool_name} {description} {category} {' '.join(tags or [])}".lower(),
        }

    def find_tools(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        """Score and return the top-k most relevant tools for a user query."""
        if not self._tools:
            return []

        tokens = re.findall(r"\w+", query.lower())
        scored: list[tuple[float, dict[str, Any]]] = []

        for name, meta in self._tools.items():
            blob = meta["search_blob"]
            score = 0.0

            # Exact name match bonus
            if name.lower() in query.lower():
                score += 10.0

            # Token overlap scoring
            for tok in tokens:
                if tok in name.lower():
                    score += 5.0
                elif tok in blob:
                    score += 2.0

            if score > 0:
                scored.append((score, meta))

        # Sort descending by score
        scored.sort(key=lambda x: x[0], reverse=True)
        return [item[1] for item in scored[:top_k]]


class FindToolsTool(BaseTool):
    """Meta-tool exposing tool search to the model."""

    name = "find_tools"
    description = (
        "Search registered tools by task description or keyword when the right tool is not in current context."
    )
    category = ToolCategory.CORE
    risk = RiskLevel.SAFE
    timeout_s = 5
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "What capability or action you are looking for"}
        },
        "required": ["query"],
    }

    def __init__(self, index: ToolDiscoveryIndex | None = None) -> None:
        self.index = index or ToolDiscoveryIndex()

    async def run(self, args: dict[str, Any]) -> ToolResult:
        return await self.execute(**args)

    async def execute(self, **kwargs: Any) -> ToolResult:
        query = kwargs.get("query", "")
        matches = self.index.find_tools(query, top_k=5)
        if not matches:
            return ToolResult.ok(f"No specific tools found matching '{query}'.")

        summary_lines = [f"- {m['name']}: {m['description']} ({m['category']})" for m in matches]
        return ToolResult.ok(
            f"Found {len(matches)} matching tools:\n" + "\n".join(summary_lines),
            tools=[m["name"] for m in matches],
        )
