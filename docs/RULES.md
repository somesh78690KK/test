# T.A.R.O. - Rules

**Version:** 1.2.0 (Draft)

These rules bind both contributors and the T.A.R.O. runtime. Some are enforced by code (marked **[code]**); the rest are review rules (marked **[review]**).

---

## 1. Python and Tooling

- Python 3.12+. **[code]** checked in CI and at startup.
- Formatting: black, line length 100, target py312. **[review]**
- Imports: isort with profile black. Groups: stdlib, third-party, first-party. **[review]**
- Lint: flake8, max line 100, ignore E203 and W503. **[review]**
- Types: mypy with `disallow_untyped_defs = true`. Every public function is typed. **[review]**
- Docstrings: Google style on every public class and function. **[review]**
- Max file length 800 lines. Max function length 60 lines. **[review]**
- Double quotes. Four-space indent. No trailing whitespace. **[review]**

## 2. Architecture

- One orchestrator. New capabilities are tools or skills, never new agents. **[review]**
- Dependencies point downward (see ARCHITECTURE section 3). **[review]**
- Only the `winapi/` package may import pywin32, pywinauto, or pynput. **[code]** enforced by an import-lint test (`tests/test_import_rules.py`).
- The UI never calls a capability directly. It sends messages to the core. **[review]**
- No keyword pre-router that bypasses the model for commands. Routing goes through tool schemas. **[review]**

## 3. Tools and Skills

- Every tool declares `name`, `description`, `parameters`, `risk`, `category`, and `timeout_s`. **[code]** the registry refuses to register a tool without them.
- Every tool returns a `ToolResult` with `status`, `output`, and `error`. Exceptions are caught and converted. **[code]**
- A tool never reports success on partial failure. **[review]**
- Skills must pass `skill.json` validation before loading. **[code]**
- A skill's declared permissions must be granted before it loads. **[code]**

## 4. Safety (non-negotiable)

- Every tool call passes the risk gate. No bypass flag exists in the code. **[code]**
- HIGH and CRITICAL actions require typed confirmation of the exact action. **[code]**
- Deletes and overwrites of user files are at least HIGH. Deletes under system paths are CRITICAL. **[code]**
- Registry writes export a backup first. **[code]**
- Code execution is limited to `sandbox/` with a timeout. **[code]**
- Admin elevation is requested per action through UAC. The app never runs as admin by default. **[code]**
- The kill switch must stop tool execution within 1 s. **[code]** tested in TASK-036.
- No outbound network calls unless a cloud feature is enabled in config. **[code]**
- Secrets come from `.env` only. No keys in source, config, logs, or prompts. **[code]** via secret scanner in CI.

## 5. Agent Behaviour (runtime rules for the model)

These are written into the system prompt and checked by the response builder.

1. The status of every action comes from the tool result, shown in a code-generated status block that the model cannot edit. **[code]**
2. When a tool fails, report the tool name, the exact error text, and one next step. Do not invent a cause. **[review]**
3. Never claim a capability is missing if a registered tool covers it. Check the tool list first. **[review]**
4. When a request is ambiguous and the action is MEDIUM or higher, ask one question. For SAFE and LOW actions, act and state what was done. **[review]**
5. Describe images only with what is visible. If unsure, say "unclear" and give the reason. **[review]**
6. No greetings or sign-offs except the time-aware opener on the first turn of a session. **[review]**
7. Answers come from tool results or the model's knowledge. Web facts must cite the source URL. **[review]**
8. Refusals are short: name the blocked action, the reason, and the nearest allowed option. **[review]**

The earlier TARO docs asked for an "unaligned" model with no safety filters. That is not carried into T.A.R.O. Safety is enforced by the permission and confirmation system above. The model's persona does not change that.

## 6. Memory and Privacy

- Only store what the user states or what a tool returns. Never store inferred personal traits. **[review]**
- Screenshots and camera frames are not written to disk unless the user asks. **[code]**
- Audit log entries mask secrets. **[code]**
- The user can view, edit, and delete any memory entry from the HUD. **[code]**
- Memory deletion removes the SQLite rows, the ChromaDB entries, and the JSON records together. **[code]**

## 7. Testing

- Unit tests for every tool and every safety rule. Coverage target: 80% overall, 100% on `core/safety/` and `core/tools/registry.py`. **[code]** via CI.
- Integration tests for the orchestrator loop using a fake model that returns scripted tool calls. **[review]**
- Each TASK in TASKS.md has an acceptance test. A task is not Done without it. **[review]**
- Benchmarks run on the target laptop only. Results are committed to `docs/benchmarks.md`. **[review]**

## 8. Git and Reviews

- Branch names: `feat/`, `fix/`, `docs/`, `chore/`.
- Commit messages: imperative mood, subject under 72 characters.
- Every change updates the relevant doc (PRD, ARCHITECTURE, TASKS). **[review]**
- No direct commits to `main`. One reviewer (may be the owner for solo work, with a self-check list). **[review]**

## 9. Documentation

- Docs use the same version number as the code.
- No doc claims a feature is "complete" unless its TASK has passed its acceptance test. The status in TASKS.md is the source of truth.
- Benchmarks replace guesses. Any number in docs with no benchmark behind it is marked "estimate".

## 10. Error Handling

- Specific exception classes per area (`ModelError`, `ToolError`, `PermissionDenied`, `SafetyBlock`). No bare `except:`. **[review]**
- Errors are logged with context and surfaced to the user with the exact message. **[review]**
- Retries: at most 2, with exponential backoff, only for network and model-busy errors. **[code]**

## 11. Self-Extension Rules (Skill Forge)

1. T.A.R.O. builds a skill only after the user says yes to building it. A detected gap is an offer, not an action. **[code]**
2. Two approvals (spec, then code and tests) are required in default mode. **[code]**
3. Generated code must pass the AST static check against `skill_allowlist.json`. **[code]**
4. Generated code is tested in the sandbox before it can be registered. **[code]**
5. The Forge cannot write to `core/`, `config/permissions.json`, `.env`, the allowlist, trusted actions, or audit logs. **[code]** enforced by the write broker, read-only NTFS permissions set by the installer, and a startup hash check (SELF_EXTENSION section 4).
6. A skill's risk and permissions are set by static analysis and the user-approved spec. The skill cannot change them. **[code]**
7. New skills start in `trial` and require confirmation for the first 3 uses. **[code]**
8. Only the user can edit the allowlist. **[code]**
9. The Forge never edits a skill it did not create. **[code]**
10. A skill whose manifest hash changed after registration is disabled until re-approved. **[code]**
11. Every Forge action is written to the audit log. **[code]**
12. No setting turns off the static check or the immutable-path rule. **[code]**

## 12. Tool Discovery Rules

- Tool descriptions must be one sentence, under 30 words, and say what the tool does and when to use it. **[review]**
- A tool family may have at most 15 actions. Larger sets are split. **[review]**
- Tool names are verbs or `family.action` (`file.copy`, `browser.new_tab`). **[review]**

## 13. Background Services

- Optional services (guardians, watcher) are off by default and need explicit user opt-in per service. **[code]**
- A service has a CPU budget; exceeding it pauses the service and logs it. **[code]**
- A service never executes an action without the risk gate. **[code]**

## 14. Untrusted Content

1. Anything not typed or spoken by the user (web pages, files, OCR text, notifications, tool output) is wrapped as untrusted data before it reaches the model. **[code]**
2. Risk levels come from the tool and its arguments, never from model output. **[code]**
3. If untrusted content entered the context in this request, MEDIUM, HIGH, and CRITICAL actions always show the confirmation card, even for trusted actions. **[code]**
4. The card shows the source of any copied text (URL, path, command). **[code]**
5. Guardians and web research produce drafts, never direct tool calls. **[code]**

## 15. Local Interface Security

1. Servers bind to `127.0.0.1` only. **[code]**
2. Every WebSocket and HTTP request carries a per-session random token and an allowed `Origin`. **[code]** tested with a request from a different origin.
3. The HUD loads only local files. No remote scripts, fonts, or images. **[code]**
4. Ollama is bound to `127.0.0.1` and `OLLAMA_MAX_LOADED_MODELS=1` is set at launch. **[code]** checked by `taro.doctor`.

## 16. Skill Isolation

1. Forge-created and user-added skills run in a skill host subprocess with a Job Object, a clean environment, a timeout, and `workspace/` as the working directory. **[code]**
2. Skill subprocesses get no API keys and no `.env`. **[code]**
3. Killing the core kills all skill hosts. **[code]**
4. Network use raises a skill's computed risk to at least MEDIUM. **[code]**

## 17. Capture, Recording, and Privacy

1. Windows listed in `capture_exclude_titles` are never captured. **[code]**
2. The training recorder pauses on password fields and never stores those keystrokes. **[code]**
3. Recording always shows a visible indicator. **[code]**
4. Paths are handled with `pathlib` only, never by string concatenation. Tests include paths with spaces and non-ASCII characters. **[review]** with a test fixture.

## 18. Documentation Integrity

1. `python scripts/check_docs.py` must pass before any doc change is merged. It checks versions, task dependencies, references, section numbering, and stdlib-shadowing package names. **[code]**
2. A doc change that adds or renames a task, requirement, or file updates every doc that mentions it. **[review]**
3. Risks found during development are added to RISKS_AND_TROUBLESHOOTING.md in the same change that fixes them. **[review]**
