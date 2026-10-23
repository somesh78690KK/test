"""Execution template for api skills."""

from typing import Any
import httpx


def run(args: dict[str, Any]) -> dict[str, Any]:
    endpoint = args.get("endpoint", "")
    if not endpoint:
        return {"status": "error", "error": "Missing endpoint parameter."}

    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(endpoint)
            return {
                "status": "ok",
                "output": f"API response from {endpoint}: HTTP {resp.status_code}",
                "status_code": resp.status_code,
                "data": resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {},
            }
    except Exception as e:
        return {"status": "error", "error": f"API call failed: {e}"}
