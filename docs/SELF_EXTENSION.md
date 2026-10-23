# T.A.R.O. - Self-Extension (Skill Forge)

**Version:** 1.2.0 (Draft)

Goal: when the user says "add a skill that does X" or asks for something T.A.R.O. cannot do, T.A.R.O. builds, tests, and registers a new skill. It does this without a developer.

This feature runs code that the model wrote, so it has the strictest safety rules in the project. Those rules are part of the design, not optional.

---

## 1. Trigger Paths

1. **Explicit:** "Create a skill that renames my photos by date."
2. **Gap detection:** The model cannot find a tool (`find_tools` returns nothing relevant). T.A.R.O. says what is missing and offers to build it: "I have no tool for this. I can create one. Build it?" It never builds without the user's yes.
3. **Repair:** A skill fails repeatedly (3 failures in a row). T.A.R.O. offers to fix it.

## 2. Pipeline

```
request
  └─ 1. CLARIFY     one question max, only if inputs/outputs are unclear
  └─ 2. SPEC        write skill.json draft: name, description, inputs, outputs,
  │                 risk, permissions needed, side effects
  └─ 3. PREVIEW     show spec to user: "This skill will read folder X and rename files. Risk: HIGH." → user approves spec
  └─ 4. GENERATE    write execution.py from the skill template (+ SKILL.md + tests)
  └─ 5. STATIC CHECK  AST scan against the allowlist (section 3)
  └─ 6. TEST        run generated tests + dry run in sandbox with fake inputs
  └─ 7. REVIEW      show code diff + test results to user → user approves
  └─ 8. REGISTER    copy to skills/_generated/<name>/, validate, hot-load, record in audit log
  └─ 9. MONITOR     track success rate; offer repair on repeated failure
```

Steps 3 and 7 are two separate approvals. Neither can be skipped in default mode.

## 3. Static Check (Step 5)

The skill code is parsed with `ast`. This is a **filter that catches obvious mistakes and obvious abuse. It is not a security boundary**, because Python offers many indirect routes to the same functions. The real containment is out-of-process execution (ARCHITECTURE section 25), user review, and the risk level. The code is rejected if it does any of the following:

- Imports a module not in `config/skill_allowlist.json` (default: a small stdlib subset such as `pathlib`, `json`, `csv`, `datetime`, `re`, plus `openpyxl`, `python-docx`, and `pillow`; the user can add others such as `requests` or `pandas` after reading what they can do).
- Calls `eval`, `exec`, `compile`, `__import__`, `os.system`, `subprocess` with `shell=True`, `ctypes`, or raw socket APIs.
- Touches paths in `core/`, `config/permissions.json`, `.env`, `data/procedural/trusted_actions.json`, or `logs/audit/`.
- Writes outside `workspace/` unless the spec declares a path and the user approved that path.
- Makes network calls to hosts not listed in the spec (declared hosts shown to the user).

The allowlist is edited by the user only. T.A.R.O. cannot add to it.

## 4. Hard Boundaries (Immutable)

T.A.R.O. can never create or edit:
- `core/safety/` (risk, permissions, confirmation, audit, kill switch)
- `core/tools/registry.py` validation rules
- `config/permissions.json`, `.env`, the allowlist, or the trusted-actions file
- Another skill that it did not create (user-made and built-in skills are read-only to the Forge)

How this is enforced, honestly: (1) Forge writes go through a broker that rejects any path outside `skills/_generated/` and `sandbox/forge/`. (2) The installer sets read-only NTFS permissions on `core/` and `config/` for the normal user (one-time admin step). (3) The registry verifies a SHA-256 manifest of protected files at every start and refuses to run if they changed. (4) Skills run out of process (ARCHITECTURE section 25). A user with admin rights can still change these files by hand; that is the user's choice and is logged.

A new skill:
- Gets the risk level its static analysis and spec imply. The code, not the model, sets the risk (file delete anywhere means at least HIGH; network means at least MEDIUM).
- Can never lower its own risk or grant itself permissions.
- Starts as `trial`: runs only with confirmation for the first 3 uses, regardless of risk, then moves to `active` if all 3 succeed and the user did not revoke it.

## 5. Skill Format

```
skills/<name>/
  SKILL.md        what it does, when to use, examples
  skill.json      schema and metadata (below)
  execution.py    run(args: dict) -> dict    # status, output, error
  tests/test_skill.py
  CHANGELOG.md    created_by (user request text), approvals, versions
```

`skill.json`:

```json
{
  "name": "rename_photos_by_date",
  "version": "1.0.0",
  "description": "Rename image files in a folder using their capture date.",
  "category": "files",
  "risk": "HIGH",
  "permissions": ["files.read", "files.write"],
  "paths": ["workspace/photos"],
  "network_hosts": [],
  "inputs": {"type": "object", "properties": {"folder": {"type": "string"}}, "required": ["folder"]},
  "outputs": {"type": "object", "properties": {"renamed": {"type": "integer"}}},
  "origin": "forge",
  "state": "trial",
  "created_at": "2026-10-22T10:00:00Z"
}
```

## 6. Generation Strategy for a 4B Model

A small model writes better code from structure than from a blank page.

1. **Templates:** Start from `skills/_templates/` (file skill, web skill, Excel skill, text skill, API skill). The model fills in `run()`.
2. **Few-shot:** Include two existing, working skills of the same category in the prompt.
3. **Small units:** One skill does one thing. Anything bigger is split into a plan of several skills.
4. **Retry loop:** If static check or tests fail, the error goes back to the model. Max 3 attempts. After that T.A.R.O. reports the failure and the last error.
5. **Optional cloud draft:** If enabled, a larger cloud model drafts `execution.py`. The same static check, tests, and user review still apply. Sent data: the spec only, never memory.

## 7. Adding Capabilities Without Code

- **MCP servers:** "Connect the GitHub MCP server." The user supplies the server command. T.A.R.O. registers its tools through the same risk gate. MCP tools start at MEDIUM risk until reviewed.
- **Workflow skills:** Combine existing tools into a named workflow ("morning setup"). This needs no new code, so it skips steps 4 to 6.
- **Prompt skills:** A reusable instruction (no code), such as "summarize meeting notes in this format".

## 8. User Controls

- Skills tab: list, state (trial, active, disabled), success rate, last run, origin.
- Actions: disable, delete, view source, export, revert to a previous version.
- **Mode setting** (Settings → Skills):
  - `ask` (default): both approvals required.
  - `trusted-low`: skills whose computed risk is SAFE or LOW can skip step 7 review (static check and tests still run). HIGH and CRITICAL always require both approvals.
  - There is no mode that skips static checks or the immutable-path rule.

## 9. Audit

Every Forge action is logged: request text, spec, generated code hash, static check result, test result, approvals, registration, and every later run. The skill's `CHANGELOG.md` shows the same history.

## 10. Failure Handling

| Failure | Behaviour |
| :--- | :--- |
| Static check fails after 3 attempts | Report the violation. Offer a safer variant (for example, read-only version). |
| Tests fail after 3 attempts | Report failing tests and stop. Skill is not registered. |
| User denies approval | Delete draft. Log the denial. |
| Skill name conflicts | Ask for a new name; never overwrite. |
| Skill crashes at runtime | Return the exact error, mark a failure, offer repair after 3. |
| Forge process error | Draft folder removed; nothing is registered. |

## 11. Acceptance Tests (see TASKS Phase 6b)

1. "Create a skill that counts words in a text file." → spec, approval, tests, review, registered, callable.
2. A generated skill that imports `subprocess` with `shell=True` is rejected by the static check.
3. A generated skill that writes to `core/safety/` is rejected, and the immutable-path check blocks it even if the AST scan is bypassed.
4. A skill cannot raise its own permissions after registration (hash and manifest verified on every load).
5. Denying approval at step 3 or 7 leaves no files behind.
6. `trial` skill asks for confirmation on its first 3 runs, then becomes `active`.
7. Killing the process mid-generation leaves no half-registered skill.
8. A forge-created skill runs in a skill host subprocess. Killing the core (or pressing the kill switch) kills the skill host.
9. A skill host process cannot see API keys from the core's environment.
10. A skill that exceeds its time or memory limit is killed and reported with the exact limit.
