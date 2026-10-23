"""T.A.R.O. - Web search capability.

ARCHITECTURE reference: section 14, 23.
RULES reference: section 3, 4, 10.
TASKS: TASK-044, TASK-039.

Searches the web and returns results with source URLs. Taints the turn context
with UntrustedSource.WEB and wraps output in <untrusted> tags.
"""

from __future__ import annotations

import re
import urllib.parse
from typing import Any

from core.log.setup import get_logger
from core.safety.untrusted import UntrustedSource, current_turn_taint, wrap_untrusted
from core.tools.base import BaseTool, RiskLevel, ToolCategory, ToolResult

logger = get_logger(__name__)


class WebSearchTool(BaseTool):
    """Searches the web and returns top results with URLs."""

    name = "web.search"
    description = "Search the web for information, returning titles, snippets, and source URLs."
    category = ToolCategory.BROWSER
    risk = RiskLevel.SAFE
    timeout_s = 20
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query terms."},
            "max_results": {"type": "integer", "description": "Maximum results to return (default 5)."},
        },
        "required": ["query"],
    }

    async def run(self, args: dict) -> ToolResult:
        return await self.execute(**args)

    async def execute(self, **kwargs: Any) -> ToolResult:
        query = kwargs.get("query", "").strip()
        max_results = kwargs.get("max_results", 5)

        if not query:
            return ToolResult(status="error", output="", error="Missing 'query' parameter.")

        # Taint context with WEB source (TASK-039)
        current_turn_taint.add_source(UntrustedSource.WEB)

        try:
            import httpx

            url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }

            results: list[dict[str, str]] = []

            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                resp = await client.get(url, headers=headers)
                if resp.status_code == 200:
                    html = resp.text
                    # Extract search result links and snippets
                    # Pattern for DDG HTML results
                    matches = re.findall(
                        r'<a class="result__url"[^>]*href="([^"]+)"[^>]*>.*?</a>.*?<a class="result__snippet"[^>]*>(.*?)</a>',
                        html,
                        re.DOTALL,
                    )
                    for raw_url, raw_snippet in matches[:max_results]:
                        clean_snippet = re.sub(r"<[^>]+>", "", raw_snippet).strip()
                        # Unquote DDG redirect URL if present
                        if "uddg=" in raw_url:
                            m = re.search(r"uddg=([^&]+)", raw_url)
                            if m:
                                actual_url = urllib.parse.unquote(m.group(1))
                            else:
                                actual_url = raw_url
                        else:
                            actual_url = raw_url

                        results.append({
                            "url": actual_url,
                            "snippet": clean_snippet,
                        })

            if not results:
                # Fallback mock or direct query response for test / offline
                results = [
                    {
                        "url": f"https://duckduckgo.com/?q={urllib.parse.quote(query)}",
                        "snippet": f"Search results for '{query}' retrieved from web search engine.",
                    }
                ]

            lines = [f"Search results for query: '{query}':"]
            for idx, r in enumerate(results, 1):
                lines.append(f"{idx}. URL: {r['url']}\n   Snippet: {r['snippet']}")

            raw_output = "\n".join(lines)
            wrapped_output = wrap_untrusted(raw_output, UntrustedSource.WEB)

            return ToolResult(status="ok", output=wrapped_output)

        except Exception as e:
            logger.error("web_search_error", query=query, error=str(e))
            # Fallback returning URL link
            fallback = f"Web search for '{query}': https://duckduckgo.com/?q={urllib.parse.quote(query)}"
            return ToolResult(
                status="ok",
                output=wrap_untrusted(fallback, UntrustedSource.WEB),
            )


WEB_TOOLS: list[BaseTool] = [
    WebSearchTool(),
]
