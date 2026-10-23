"""T.A.R.O. - Web page fetch and text extraction capability.

ARCHITECTURE reference: section 14, 23.
RULES reference: section 3, 4, 10.
TASKS: TASK-044, TASK-039.

Fetches web pages, extracts clean readable text, strips malicious scripts,
taints the turn context with UntrustedSource.WEB, and wraps output in <untrusted>.
"""

from __future__ import annotations

import re
from typing import Any

from core.log.setup import get_logger
from core.safety.untrusted import UntrustedSource, current_turn_taint, wrap_untrusted
from core.tools.base import BaseTool, RiskLevel, ToolCategory, ToolResult

logger = get_logger(__name__)

MAX_PAGE_CHARS = 10000


class WebFetchTool(BaseTool):
    """Fetches a web page and returns readable text."""

    name = "web.fetch"
    description = "Fetch and extract clean readable text from a URL."
    category = ToolCategory.BROWSER
    risk = RiskLevel.SAFE
    timeout_s = 20
    parameters = {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "The URL to fetch."}
        },
        "required": ["url"],
    }

    async def run(self, args: dict) -> ToolResult:
        return await self.execute(**args)

    async def execute(self, **kwargs: Any) -> ToolResult:
        url = kwargs.get("url", "").strip()
        if not url:
            return ToolResult(status="error", output="", error="Missing 'url' parameter.")

        # Taint context with WEB source (TASK-039)
        current_turn_taint.add_source(UntrustedSource.WEB)

        try:
            import httpx

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }

            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                resp = await client.get(url, headers=headers)
                if resp.status_code != 200:
                    return ToolResult(
                        status="error",
                        output="",
                        error=f"HTTP {resp.status_code} while fetching {url}",
                    )

                html = resp.text

            # Clean HTML to plain text
            # Strip script and style tags
            clean = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", html, flags=re.DOTALL | re.IGNORECASE)
            # Strip all remaining tags
            text = re.sub(r"<[^>]+>", " ", clean)
            # Normalize whitespace
            text = re.sub(r"\s+", " ", text).strip()

            if len(text) > MAX_PAGE_CHARS:
                text = text[:MAX_PAGE_CHARS] + f"\n\n[TRUNCATED: Exceeded {MAX_PAGE_CHARS} character limit]"

            raw_output = f"Source URL: {url}\n\nContent:\n{text}"
            wrapped_output = wrap_untrusted(raw_output, UntrustedSource.WEB)

            return ToolResult(status="ok", output=wrapped_output)

        except Exception as e:
            logger.error("web_fetch_error", url=url, error=str(e))
            return ToolResult(status="error", output="", error=f"Failed to fetch URL '{url}': {e}")


WEB_FETCH_TOOLS: list[BaseTool] = [
    WebFetchTool(),
]
