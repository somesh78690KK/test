"""Execution template for web skills."""

from typing import Any
import httpx


def run(args: dict[str, Any]) -> dict[str, Any]:
    url = args.get("url", "")
    if not url:
        return {"status": "error", "error": "Missing URL parameter."}

    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(url)
            return {
                "status": "ok",
                "output": f"Fetched {url} with status {resp.status_code} ({len(resp.text)} chars).",
                "status_code": resp.status_code,
            }
    except Exception as e:
        return {"status": "error", "error": f"Failed to fetch {url}: {e}"}
