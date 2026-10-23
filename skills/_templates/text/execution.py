"""Execution template for text skills."""

from typing import Any


def run(args: dict[str, Any]) -> dict[str, Any]:
    text = args.get("text", "")
    lines = text.strip().splitlines()
    words = text.split()
    return {
        "status": "ok",
        "output": f"Analyzed text: {len(characters := text)} chars, {len(words)} words, {len(lines)} lines.",
        "word_count": len(words),
        "char_count": len(characters),
    }
