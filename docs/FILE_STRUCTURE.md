# T.A.R.O. - File Structure

**Version:** 1.2.0 (Draft)

---

## 1. Repository Tree

```
TARO/
├── main.py                      # Entry point: starts core, HUD, voice workers. Subcommands: --doctor, kill
├── requirements.txt
├── requirements-dev.txt
├── pyproject.toml               # black, isort, mypy, pytest config
├── .flake8
├── .pre-commit-config.yaml
├── .env.example                 # API key template (copy to .env)
├── .gitignore
├── README.md
├── taro.spec                    # PyInstaller spec
│
├── config/
│   ├── config.yaml              # defaults (committed)
│   ├── config.local.yaml        # machine overrides (not committed)
│   ├── permissions.json         # allow / ask / deny per category (read-only to the Forge)
│   ├── skill_allowlist.json     # modules a generated skill may import (user-edited only)
│   ├── mcp_servers.json         # configured MCP servers
│   ├── apps.json                # app launch map (name -> executable or URI)
│   ├── persona.md               # system prompt sections, versioned and read by prompt_builder
│   └── Modelfile                # Ollama Modelfile for the `taro` model (no persona)
│
├── core/
│   ├── __init__.py
│   ├── orchestrator.py          # plan / act loop, step limits, grounding check
│   ├── planner.py               # task list and plan state
│   ├── intent.py                # intent schema (intent, params, confidence, risk)
│   ├── prompt_builder.py        # token-budgeted prompt assembly
│   ├── summarizer.py            # rolling summary every 5 turns
│   ├── response_guard.py        # checks success claims against tool results
│   ├── config.py                # pydantic models and loader
│   ├── events.py                # internal event types
│   ├── forge/
│   │   ├── __init__.py
│   │   ├── spec_writer.py       # skill.json draft from request
│   │   ├── generator.py         # execution.py from templates + model
│   │   ├── static_check.py      # ast scan, allowlist, path guard
│   │   ├── test_runner.py       # sandbox tests and dry run
│   │   ├── approvals.py         # two-step approval records
│   │   ├── skill_host.py        # out-of-process skill runner (Job Object, clean env, path broker)
│   │   ├── registrar.py         # copy, validate, hot-load, manifest hash
│   │   └── monitor.py           # skill health, repair offers
│   ├── discovery.py             # find_tools meta-tool, tool embeddings
│   ├── scheduler.py             # cron-like scheduler
│   ├── undo.py                  # recovery manifests, undo
│   ├── mcp_client.py            # MCP tool server connections
│   ├── model/
│   │   ├── __init__.py
│   │   ├── ollama_client.py     # streaming, tool-calling, timeouts, retry
│   │   ├── model_manager.py     # single large model, keep_alive, unload
│   │   ├── vram_monitor.py      # nvidia-smi polling
│   │   └── errors.py
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── base.py              # Tool base class, ToolResult
│   │   ├── registry.py          # registration, validation, category filter
│   │   └── schema.py            # JSON schema helpers
│   ├── safety/
│   │   ├── __init__.py
│   │   ├── risk.py              # base risk + argument escalation
│   │   ├── permissions.py       # allow / ask / deny evaluation
│   │   ├── confirmation.py      # MEDIUM yes/no, HIGH typed phrase
│   │   ├── trusted_actions.py   # approve once, revoke
│   │   ├── audit.py             # JSON-line audit writer
│   │   ├── kill_switch.py       # hotkey (own thread), HUD/tray button, `taro kill`, cancellation flag
│   │   └── untrusted.py         # untrusted-content wrapper and taint tracking
│   ├── memory/
│   │   ├── __init__.py
│   │   ├── sqlite_store.py      # Tier 1: turns, tool calls, summaries
│   │   ├── chroma_store.py      # Tier 2: semantic memory
│   │   ├── json_store.py        # Tier 3: workflows, trusted actions
│   │   └── profile.py           # reads data/profile.md
│   ├── log/                     # named `log`, not `logging`, to avoid shadowing the stdlib
│   │   ├── __init__.py
│   │   ├── setup.py             # structured logging config
│   │   └── masking.py           # secret masking filter
│   └── ws/
│       ├── __init__.py
│       ├── auth.py              # session token and Origin check
│       ├── protocol.py          # message types (chat, telemetry, tool, confirm)
│       └── server.py            # WebSocket server on 127.0.0.1, random port chosen at start
│
├── capabilities/                # Tools implemented by area
│   ├── __init__.py
│   ├── system/
│   │   ├── apps.py              # launch with process-poll verification
│   │   ├── windows.py           # minimize, maximize, restore, close, switch
│   │   ├── processes.py         # list, terminate (HIGH)
│   │   ├── hardware.py          # brightness, volume, mute, power
│   │   ├── stats.py             # CPU, RAM, GPU, VRAM, disk, net, temp
│   │   └── clipboard.py
│   ├── files/
│   │   ├── operations.py        # copy, move, rename, delete, search, read, write
│   │   ├── registry_ops.py      # backup-first registry read/write
│   │   └── workspace.py         # path guard for workspace root
│   ├── web/
│   │   ├── search.py            # search API / DuckDuckGo, returns URLs
│   │   ├── fetch.py             # page fetch and text extraction
│   │   ├── browser.py           # Playwright control
│   │   └── cdp.py               # attach to running Chrome via CDP
│   ├── office/
│   │   ├── excel.py             # openpyxl + live Excel (pywin32)
│   │   ├── word.py              # python-docx
│   │   └── powerpoint.py        # python-pptx
│   ├── vision/
│   │   ├── capture.py           # mss capture, scale, in-memory JPEG
│   │   ├── ocr.py               # pytesseract
│   │   ├── vlm.py               # on-demand vision model + validator
│   │   └── camera.py            # WebRTC frame or OpenCV fallback
│   ├── coding/                  # named `coding`, not `code`, to avoid shadowing the stdlib
│   │   ├── sandbox.py           # run scripts in sandbox/ with timeout
│   │   └── generate.py          # script drafting helpers
│   ├── training/
│   │   ├── recorder.py          # pynput hooks, JSON-line events
│   │   ├── compiler.py          # raw events -> workflow.json
│   │   └── replayer.py          # per-step window verification
│   ├── reminders/
│   │   └── timers.py
│   ├── notes/
│   │   └── notes.py
│   ├── cloud/                   # opt-in only
│   │   ├── image_gen.py
│   │   └── gemini_override.py
│   ├── ui_control/
│   │   ├── ui_act.py            # autonomous UI loop (max 10 steps)
│   │   ├── uia_tree.py          # UI Automation tree and element search
│   │   └── keyboard_mouse.py    # keys, hotkeys, clicks, gestures
│   ├── app_intel/
│   │   ├── monitor.py           # app and window tracking
│   │   ├── discovery.py         # installed app discovery, aliases
│   │   └── lifecycle.py
│   ├── shell/
│   │   ├── runner.py            # PowerShell and CMD, templates
│   │   └── templates.json
│   ├── guardians/               # optional services, off by default
│   │   ├── security.py
│   │   └── notifications.py
│   ├── analytics/
│   │   └── usage.py
│   └── docs_qa/
│       └── index.py             # PDF/DOCX/TXT indexing for Q&A
│
├── voice/
│   ├── __init__.py
│   ├── wake_word.py             # "taro" detection (CPU)
│   ├── stt.py                   # faster-whisper (CPU), Google fallback (consent)
│   ├── tts.py                   # edge-tts, pyttsx3 fallback
│   ├── audio_worker.py          # playback queue (pygame)
│   └── mic_test.py
│
├── skills/                      # Skill folders (loaded at startup)
│   ├── README.md                # skill authoring guide
│   ├── _templates/              # Forge templates: file, web, excel, text, api
│   ├── _generated/              # Forge-created skills (state: trial or active)
│   ├── excel_automation/
│   │   ├── SKILL.md
│   │   ├── skill.json
│   │   └── execution.py
│   ├── file_organizer/
│   ├── system_info/
│   ├── clipboard_tools/
│   ├── screenshot_tool/
│   ├── web_research/
│   ├── note_taking/
│   ├── reminders/
│   ├── timers/
│   └── workflow_runner/
│
├── winapi/                      # ONLY place allowed to import pywin32 / pywinauto / pynput.
│   ├── __init__.py              # Named `winapi`, not `platform`, to avoid shadowing the stdlib.
│   ├── win32_windows.py
│   ├── uia.py                   # pywinauto UI Automation
│   ├── input_hooks.py           # pynput
│   ├── hotkey.py                # RegisterHotKey for the kill switch (own thread)
│   └── registry.py
│
├── ui/
│   ├── desktop_wrapper.py       # PyWebView window
│   ├── server.py                # local HTTP server for static files
│   ├── html/
│   │   └── taro_hud.html        # single-file HUD (inline CSS/JS)
│   └── assets/
│       ├── icons/
│       └── sounds/
│
├── data/                        # runtime data (not committed)
│   ├── taro.db                  # SQLite
│   ├── chroma/                  # ChromaDB
│   ├── procedural/
│   │   ├── workflows/           # *.json workflows
│   │   ├── trusted_actions.json
│   │   └── permission_log.json
│   ├── recovery/                # deleted/overwritten files with manifests (30 days)
│   └── profile.md               # user profile (edited by user)
│
├── models/                      # bundled embedding model and wake-word model
├── workspace/                   # default writable root for file tools
├── sandbox/                     # code execution working dir
├── cache/                       # temporary model/OCR cache
├── temp/                        # short-lived files, cleared on start
├── logs/                        # not committed
│   ├── core/
│   ├── model/
│   ├── tools/
│   ├── voice/
│   ├── vision/
│   ├── safety/
│   └── audit/                   # audit JSON lines
│
├── docs/
│   ├── PRD.md
│   ├── DESIGN.md
│   ├── ARCHITECTURE.md
│   ├── RULES.md
│   ├── TASKS.md
│   ├── FILE_STRUCTURE.md
│   ├── MEMORY.md
│   ├── CAPABILITY_PARITY.md
│   ├── SELF_EXTENSION.md
│   ├── SETUP.md
│   ├── RISKS_AND_TROUBLESHOOTING.md
│   ├── benchmarks.md            # filled by TASK-011 and TASK-021
│   └── security-review.md       # filled by TASK-091
│
├── tests/
│   ├── unit/
│   │   ├── core/
│   │   ├── safety/
│   │   ├── tools/
│   │   ├── capabilities/
│   │   └── skills/
│   ├── integration/
│   │   ├── test_orchestrator_loop.py   # scripted fake model
│   │   └── test_confirmation_flow.py
│   ├── e2e/
│   │   └── test_voice_to_action.py
│   ├── fixtures/
│   │   ├── fake_model.py
│   │   ├── sample_frames/       # 640x360 test images
│   │   └── golden/              # expected workflow JSON, etc.
│   └── test_import_rules.py     # enforces platform adapter import rule
│
└── scripts/
    ├── build.bat                # PyInstaller build
    ├── create_model.bat         # ollama create taro
    ├── benchmark_model.py       # TASK-011
    ├── benchmark_vision.py      # TASK-021
    ├── protect_install.bat      # TASK-125 (needs admin once)
    ├── secret_scan.py           # TASK-038
    └── check_docs.py            # doc consistency checker (TASK-007)
```

## 2. Naming Rules

- Packages and modules: `snake_case`.
- Classes: `PascalCase`. Tool classes end with `Tool` (for example `LaunchAppTool`).
- Config keys: `snake_case`. Environment variables: `TARO_` prefix (for example `TARO_GEMINI_API_KEY`).
- Skill folders: `snake_case`. Skill `name` in `skill.json` matches the folder name.
- Doc files: upper snake case in `docs/` (for example `PRD.md`).
- Never name a package after a Python stdlib module (`platform`, `logging`, `code`, `json`, `queue`, `types`, `email`, `select`). `scripts/check_docs.py` and the import-lint test both check this.

## 3. Ignore Rules (`.gitignore`)

```
.env
config/config.local.yaml
data/
logs/
cache/
temp/
sandbox/
workspace/
venv/
__pycache__/
*.pyc
dist/
build/
```

## 4. Files Created at Runtime

| Path | Created by | Created when |
| :--- | :--- | :--- |
| `data/taro.db` | sqlite_store | First run |
| `data/chroma/` | chroma_store | First memory write |
| `data/profile.md` | profile | First run, from template |
| `data/procedural/trusted_actions.json` | trusted_actions | First approval |
| `logs/audit/YYYY-MM-DD.jsonl` | audit | First tool call of the day |
| `workspace/`, `sandbox/` | setup | First run |

## 5. Size Limits

- Source file: 800 lines maximum (see RULES section 1).
- Skill folder: under 2 MB, excluding bundled test data.
- Logs: rotate at 10 MB, keep 7 days.
- Audit: never auto-deleted (user can export or clear from HUD).
