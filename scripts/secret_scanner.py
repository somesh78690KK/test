#!/usr/bin/env python3
"""T.A.R.O. - Secret Scanner.

ARCHITECTURE reference: section 14.
TASKS: TASK-038.

Scans files for committed API keys, tokens, and private credentials.
Exits 0 if clean, exits 1 if secret matches are discovered.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import NamedTuple

# Common high-entropy or provider-specific secret patterns
SECRET_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("OpenAI API Key", re.compile(r"\bsk-[a-zA-Z0-9_-]{24,}\b")),
    ("Anthropic API Key", re.compile(r"\bsk-ant-[a-zA-Z0-9_-]{32,}\b")),
    ("Google AI / Gemini Key", re.compile(r"\bAIzaSy[a-zA-Z0-9_-]{33}\b")),
    ("HuggingFace Token", re.compile(r"\bhf_[a-zA-Z0-9]{34,}\b")),
    ("AWS Access Key ID", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("GitHub Token", re.compile(r"\b(ghp|gho|ghu|ghs|ghr)_[a-zA-Z0-9]{36}\b")),
    ("Slack Token", re.compile(r"\bxox[baprs]-[0-9a-zA-Z]{10,48}\b")),
    (
        "Generic API Secret Assignment",
        re.compile(
            r"""(?i)(api[_-]?key|secret[_-]?key|auth[_-]?token|access[_-]?token)\s*=\s*["']([a-zA-Z0-9_\-]{20,})["']"""
        ),
    ),
    (
        "Private Key Header",
        re.compile(r"-----BEGIN\s+(RSA|OPENSSH|EC|DSA|PGP|PRIVATE)\s+KEY-----"),
    ),
]

IGNORED_DIRS = {
    ".git",
    ".pytest_cache",
    ".mypy_cache",
    "venv",
    ".venv",
    "__pycache__",
    "data",
    "logs",
}

IGNORED_FILES = {
    ".env.example",
    "package-lock.json",
    ".coverage",
}

# Values known to be safe fixtures or placeholders
ALLOWLIST_VALUES = {
    "your_gemini_api_key_here",
    "your_openai_api_key_here",
    "your_token_here",
    "dummy_key",
    "test_key",
    "mock_key",
    "fake_api_key",
    "PLACEHOLDER",
}


class SecretMatch(NamedTuple):
    file_path: Path
    line_number: int
    pattern_name: str
    preview: str


def scan_file(file_path: Path) -> list[SecretMatch]:
    """Scans a single file for secret patterns."""
    matches: list[SecretMatch] = []
    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return matches

    for idx, line in enumerate(content.splitlines(), start=1):
        # Ignore comments indicating explicit test mock or allowlist
        if "pragma: allowlist secret" in line or "pragma: no-secret-scan" in line:
            continue

        for name, pattern in SECRET_PATTERNS:
            found = pattern.search(line)
            if found:
                val = found.group(0)
                # Check allowlist
                if any(allow in val.lower() for allow in ALLOWLIST_VALUES):
                    continue
                # Mask secret preview
                preview = line[:found.start()] + "***REDACTED***" + line[found.end():]
                matches.append(SecretMatch(file_path, idx, name, preview.strip()))
                break

    return matches


def scan_directory(root_dir: Path) -> list[SecretMatch]:
    """Recursively scans all valid text files in root_dir."""
    all_matches: list[SecretMatch] = []
    for path in root_dir.rglob("*"):
        if path.is_dir():
            continue
        # Check ignored dirs
        if any(ignored in path.parts for ignored in IGNORED_DIRS):
            continue
        if path.name in IGNORED_FILES or path.name.endswith((".pyc", ".png", ".jpg", ".ico", ".reg")):
            continue

        matches = scan_file(path)
        all_matches.extend(matches)

    return all_matches


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    root = Path(__file__).resolve().parent.parent
    print(f"Scanning for hardcoded secrets in {root} ...")
    matches = scan_directory(root)

    if matches:
        print("\n[!] SECURITY SCAN FAILED! Unprotected secret patterns found:")
        for m in matches:
            rel = m.file_path.relative_to(root)
            print(f"  - {rel}:{m.line_number} [{m.pattern_name}] -> {m.preview}")
        return 1

    print("[OK] Secret scan passed: no unmasked credentials or private keys detected.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
