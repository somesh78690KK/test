"""Consistency checker for the T.A.R.O. docs.

Run from repository root:  python scripts/check_docs.py
Exits 1 when it finds a problem. Checks:
  1. Every doc has the same version number.
  2. TASK IDs are unique, every dependency exists, no task depends on a later one
     (file order) or on itself, and no dependency cycles.
  3. Every TASK-xxx or FR-xx / NFR-x / D-x reference in any doc exists.
  4. Section numbers in each doc are sequential with no gaps or duplicates.
  5. Every file named in a doc cross-reference exists.
  6. Banned names that shadow Python stdlib modules are not used as package dirs.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = ROOT / "docs"
DOCS = sorted(p for p in DOCS_DIR.glob("*.md"))
problems: list[str] = []


def err(msg: str) -> None:
    problems.append(msg)


texts = {p.name: p.read_text(encoding="utf-8") for p in DOCS}

# 1. versions
versions = {}
for name, t in texts.items():
    m = re.search(r"\*\*Version:\*\*\s*([0-9.]+)", t)
    versions[name] = m.group(1) if m else None
if len(set(v for v in versions.values() if v)) > 1:
    err(f"Version mismatch across docs: {versions}")
for n, v in versions.items():
    if v is None:
        err(f"{n}: no **Version:** line")

# 2. task graph
tasks_txt = texts.get("TASKS.md", "")
rows = re.findall(r"^\|\s*(TASK-\d+)\s*\|(.*)$", tasks_txt, flags=re.M)
order: dict[str, int] = {}
deps: dict[str, list[str]] = {}
for i, (tid, rest) in enumerate(rows):
    if tid in order:
        err(f"Duplicate task ID {tid}")
    order[tid] = i
    cells = [c.strip() for c in rest.split("|")]
    dep_cell = cells[1] if len(cells) >= 5 else ""
    deps[tid] = re.findall(r"TASK-\d+", dep_cell)
for tid, ds in deps.items():
    for d in ds:
        if d not in order:
            err(f"{tid} depends on missing {d}")
        elif d == tid:
            err(f"{tid} depends on itself")
        elif order[d] > order[tid]:
            err(f"{tid} depends on {d}, which is listed later (forward dependency)")


def has_cycle() -> bool:
    seen: set[str] = set()
    stack: set[str] = set()

    def visit(n: str) -> bool:
        if n in stack:
            return True
        if n in seen:
            return False
        seen.add(n)
        stack.add(n)
        for d in deps.get(n, []):
            if d in deps and visit(d):
                return True
        stack.discard(n)
        return False

    return any(visit(n) for n in deps)


if has_cycle():
    err("Dependency cycle in TASKS.md")

# 3. references
all_task_ids = set(order)
prd = texts.get("PRD.md", "")
defined_ids = set(re.findall(r"^#{2,4}\s+((?:N?FR)-\d+a?)\b", prd, flags=re.M))
defined_ids |= set(re.findall(r"^\|\s*(D-\d+)\s*\|", prd, flags=re.M))
defined_ids |= set(re.findall(r"^\|\s*(NFR-\d+)\s*\|", prd, flags=re.M))
defined_ids |= set(re.findall(r"^\|\s*(G-\d+)\s*\|", prd, flags=re.M))
for name, t in texts.items():
    for ref in set(re.findall(r"TASK-\d+", t)):
        if ref not in all_task_ids:
            err(f"{name}: references unknown {ref}")
    for ref in set(re.findall(r"\b(N?FR-\d+a?|D-\d+)\b", t)):
        if ref not in defined_ids:
            err(f"{name}: references unknown {ref}")

# 4. section numbers
for name, t in texts.items():
    nums = [int(n) for n in re.findall(r"^##\s+(\d+)\.\s", t, flags=re.M)]
    if nums and nums != list(range(1, len(nums) + 1)):
        err(f"{name}: '## N.' sections not sequential: {nums}")

# 5. file references
for name, t in texts.items():
    for ref in set(re.findall(r"\b([A-Z_]{4,}\.md)\b", t)):
        if ref not in texts and ref not in {"SKILL.md", "README.md", "CHANGELOG.md", "TASKS.md"}:
            if not (DOCS_DIR / ref).exists() and not (ROOT / ref).exists():
                err(f"{name}: references missing file {ref}")

# 6. package names that shadow the stdlib
banned = ["platform", "logging", "json", "queue", "types", "copy", "code", "ast", "email", "select"]
tree = texts.get("FILE_STRUCTURE.md", "")
for b in banned:
    if re.search(rf"^[│ ├└─]*\s*{b}/\s", tree, flags=re.M):
        err(f"FILE_STRUCTURE.md: directory '{b}/' would shadow the Python stdlib module")

if problems:
    print("PROBLEMS FOUND:")
    for p in problems:
        print(" -", p)
    sys.exit(1)
print(f"OK: {len(DOCS)} docs, {len(order)} tasks, no problems found.")
