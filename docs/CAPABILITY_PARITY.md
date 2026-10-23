# T.A.R.O. - Capability Parity Matrix (vs J.A.R.V.I.E.S. V11)

**Version:** 1.2.0 (Draft)
**Source:** all 19 J.A.R.V.I.E.S. V11 docs, read in full for the feature lists.

Legend: ✅ in T.A.R.O. docs · ➕ added in v1.1 (was missing) · 🚀 beyond JARVIS · ⏸ deferred · ⚠️ JARVIS doc claims it, but evidence says it is not really implemented

---

## 1. Important Finding About the JARVIS Docs

The JARVIS docs describe **intended and partly implemented** features. They do not prove a feature works.

- "200+ skills" is claimed everywhere, but `memory.md` lists only an Excel skill as implemented.
- `tasks.md` marks Phases 1 to 9 complete while the JARVIS issues-and-upgrades doc lists "no automated tests" and a 1700+ line `main.py`.
- Model names and versions conflict between files.

So the docs are a good **feature list**, not a verified spec. T.A.R.O. copies the feature list and adds acceptance tests so each feature is proven, not claimed.

## 2. Tool Design Change: Families, Not 200 Tools

JARVIS lists skills such as `browser_new_tab`, `browser_close_tab`, `browser_switch_tab`, `browser_go_back`, `browser_go_forward`, `browser_page_up`, `browser_page_down` and so on, each as its own skill.

T.A.R.O. runs a 4096-token context. 200 tool schemas will not fit. So the JARVIS skill list becomes **about 45 tool families**, each with an `action` parameter:

```
browser(action="new_tab" | "close_tab" | "switch_tab" | "reopen_tab" | "back" | "forward"
        | "scroll_top" | "scroll_bottom" | "page_up" | "page_down" | "devtools" | "focus_url", ...)
```

Every JARVIS skill name maps to one `family.action`. Nothing is dropped. The model sees a few compact schemas, and a `find_tools` meta-tool loads more families on demand (see ARCHITECTURE section 17).

## 3. Parity Matrix

### 3.1 Application Control

| JARVIS skill | T.A.R.O. tool | Status |
| :--- | :--- | :--- |
| launch_application, launch_app_win_s, launch_application_by_path | `app.launch` (name, search, or path) | ✅ |
| focus_application | `app.focus` | ✅ |
| close_application_by_name, close_multiple_applications | `app.close` (names list) | ✅ |
| close_application_forcefully, terminate_process | `process.terminate` (HIGH) | ✅ |
| get_running_applications, get_application_info | `app.list`, `app.info` | ➕ |
| manage_application_priority | `process.set_priority` | ➕ |
| discover_system_applications | `app.discover` (scans Start Menu, registry uninstall keys) | ➕ |
| Application aliases (AppLifecycleController) | `config/apps.json` + `app.alias` | ➕ |
| AppMonitor (background window/process tracking) | `app.monitor` service | ➕ |

### 3.2 Window Control

| JARVIS skill | T.A.R.O. tool | Status |
| :--- | :--- | :--- |
| maximize/minimize/restore/close/resize window | `window.(maximize/minimize/restore/close/resize)` | ✅ (resize ➕) |
| Window text extraction | `window.get_text` via UI Automation | ➕ |

### 3.3 Browser

| JARVIS skill | T.A.R.O. tool | Status |
| :--- | :--- | :--- |
| browser_* (tabs, back/forward, scroll, devtools, focus URL) | `browser(action=...)` | ✅ |
| Playwright control (navigate, click, type, screenshot) | `browser.navigate/click/type/screenshot/extract` | ✅ |
| Chrome CDP bridge | `browser.attach_cdp` | ✅ |
| Web search | `web.search` | ✅ |
| Page fetch / read | `web.fetch` | ✅ |

### 3.4 File System and Explorer

| JARVIS skill | T.A.R.O. tool | Status |
| :--- | :--- | :--- |
| copy, move, rename, delete, search, read, write | `file.*` | ✅ |
| explorer_go_up/back/forward/navigate_path/new_folder/rename/select_all/open_properties/focus_address/focus_search | `explorer(action=...)` | ➕ |
| explorer_delete_permanent | `explorer.delete_permanent` (CRITICAL) | ➕ |
| File "safe mode" (confirm destructive ops) | Risk gate, always on | ✅ |
| File indexing for search | `file.index` (ChromaDB) | 🚀 |

### 3.5 Keyboard and Mouse

| JARVIS skill | T.A.R.O. tool | Status |
| :--- | :--- | :--- |
| press_key, press_hotkey, type_text, tab_navigation | `keyboard.*` | ➕ |
| click_at_coordinates, click_coordinate | `mouse.click/move/drag/scroll` | ➕ |
| Hotkey manager (register, activate, deactivate, unregister, list) | `hotkey.*` | ➕ |
| Mouse gestures (swipe, circle, zoom_in, zoom_out) | `mouse.gesture` | ➕ |

### 3.6 Office

| JARVIS skill | T.A.R.O. tool | Status |
| :--- | :--- | :--- |
| Excel: autosum, edit cell, jump data edge, next sheet, general | `excel(action=...)` | ✅ |
| Word: launch, ribbon, type, bold, save | `word(action=...)` | ✅ (ribbon/format ➕) |
| PowerPoint basics | `powerpoint(action=...)` | ✅ |
| Charts in Excel | `excel.chart` | 🚀 |
| PDF read/extract/merge | `pdf(action=...)` | 🚀 |

### 3.7 Shell and Code

| JARVIS skill | T.A.R.O. tool | Status |
| :--- | :--- | :--- |
| CMD and PowerShell execution | `shell.run` (HIGH, sandbox cwd, timeout) | ✅ |
| PowerShell templates (add, use) | `shell.template` | ➕ |
| Python sandbox | `code.run_python` | ✅ |
| Code generation | `code.generate` | ✅ |
| Self-healing code (retry with the error) | `code.fix_and_retry` (max 2) | ➕ |

### 3.8 Messaging

| JARVIS skill | T.A.R.O. tool | Status |
| :--- | :--- | :--- |
| WhatsApp (search contact, draft, send with confirmation) | `message.whatsapp` | ⏸ (PRD D-4; fragile UI automation) |
| Email / Telegram / Discord messaging | `message.*` | 🚀 later, via skill forge |

### 3.9 Vision and Perception

| JARVIS skill | T.A.R.O. tool | Status |
| :--- | :--- | :--- |
| Screen capture (full, region, window, multi-monitor) | `screen.capture` | ✅ (multi-monitor ➕) |
| OCR | `screen.ocr` | ✅ |
| UI element detection | `screen.find_elements` (UIA first, OmniParser/VLM second) | ➕ |
| Visual verification and state comparison | `screen.verify`, `screen.diff` | ➕ |
| Screen monitoring with change detection | `screen.watch` | ➕ |
| Camera analysis | `camera.analyze` | ✅ |
| Image analysis | `image.describe` | ✅ |
| VLA ReAct loop (Observe, Orient, Decide, Execute, Verify) | `ui.act` (autonomous UI loop, step-limited, confirmation on HIGH) | ➕ |

### 3.10 Voice

| JARVIS feature | T.A.R.O. | Status |
| :--- | :--- | :--- |
| Wake word, continuous listening | `voice/wake_word.py` | ✅ |
| Whisper STT, Google fallback | `voice/stt.py` | ✅ |
| Edge TTS, pyttsx3 fallback | `voice/tts.py` | ✅ |
| Mic test | `voice/mic_test.py` | ✅ |
| Voice confirmation | Confirmation flow | ✅ |

### 3.11 Memory and Learning

| JARVIS feature | T.A.R.O. | Status |
| :--- | :--- | :--- |
| 3-tier memory | MEMORY.md | ✅ |
| User behaviour learning | `memory.learn` (stated preferences only, no inference) | ✅ (adjusted) |
| Permission tracking / trusted actions | Trusted-action list | ✅ |
| Usage analytics and insights | `analytics.report` (local, tool usage, failures, timing) | ➕ |
| Transaction ledger | Audit trail | ✅ |

### 3.12 Training Mode

| JARVIS feature | T.A.R.O. | Status |
| :--- | :--- | :--- |
| Record, compile, replay, manage workflows | FR-12 | ✅ |
| Manual step marking by voice | `training.mark_step` | ➕ |
| Natural-language workflow creation | `workflow.create_from_text` | 🚀 (was JARVIS "future") |
| Workflow scheduling | `schedule.*` | 🚀 (was JARVIS "future") |

### 3.13 Security and Safety

| JARVIS feature | T.A.R.O. | Status |
| :--- | :--- | :--- |
| Permission manager, risk levels, HITL | Safety layer | ✅ |
| Kill switch (Ctrl+Alt+F12) | Kill switch | ✅ |
| Audit trail | Audit | ✅ |
| Sandboxed execution | Sandbox | ✅ |
| Active Security Guardian (60 s scan, suspicious process, Defender scan, quarantine with approval) | `guardian.security` service, off by default, quarantine needs confirmation | ➕ |
| Interactive Notification Guardian (WinRT notifications, draft replies, act on approval) | `guardian.notifications` service, off by default, experimental (Windows may refuse notification access to a plain Python process), replies need confirmation | ➕ ⚠️ |
| UAC bypass | **Not copied.** Replaced by per-action UAC elevation (RULES section 4) | ✅ (changed) |

### 3.14 AI Routing

| JARVIS feature | T.A.R.O. | Status |
| :--- | :--- | :--- |
| Model router (local vs Gemini/OpenAI/Groq/Anthropic) | `ModelRouter` with opt-in cloud providers | ➕ |
| Gemini manual override | Cloud override, per request, consent logged | ✅ |
| Image generation | `image.generate` (cloud, opt-in) | ✅ |
| Model multiplexing | Model manager | ✅ |
| Utility-based decision engine | Replaced by orchestrator planning. No agent utilities needed | ✅ (changed) |
| Performance cache (L1/L2/L3) | `ResponseCache` for deterministic read-only tool results only | ➕ |
| Streaming | Streaming | ✅ |

### 3.15 UI

| JARVIS feature | T.A.R.O. | Status |
| :--- | :--- | :--- |
| Orbital UI | Replaced by two-column HUD (no agents to orbit) | ✅ (changed) |
| Telemetry, chat, history, camera preview, keyboard shortcuts, accessibility | DESIGN.md | ✅ |
| Camera expandable viewer | HUD camera panel | ➕ |
| Toast notifications | HUD notifications | ➕ |

### 3.16 Platform and Deployment

| JARVIS feature | T.A.R.O. | Status |
| :--- | :--- | :--- |
| PyInstaller EXE, installer, update mechanism | TASK-093 | ✅ |
| Docker deployment | ⏸ | Deferred |
| Plugins directory | Covered by Skill Forge and MCP (section 4) | 🚀 |

## 4. Beyond JARVIS (🚀)

| Capability | Why it matters |
| :--- | :--- |
| **Skill Forge** (T.A.R.O. writes and registers new skills on request) | See SELF_EXTENSION.md. This is your "add a skill later" requirement. |
| **find_tools meta-tool** | Lets T.A.R.O. discover tools on demand without loading all schemas into a 4096-token window. |
| **MCP client** | Connect existing tool servers (filesystem, GitHub, databases) without writing code. |
| **Plan preview and dry run** | Show the plan before running multi-step tasks. `--dry-run` for file and system tools. |
| **Undo and rollback** | File operations move to a recycle area first. Registry writes keep backups. `undo` restores the last N actions. |
| **Self-diagnosis** | `taro.doctor` checks Ollama, models, VRAM, mic, camera, permissions, and reports fixes. |
| **Scheduler** | Cron-like workflows and reminders that survive restarts. |
| **Local document Q&A** | Index PDFs, docs, and notes for semantic recall. |
| **Evaluation harness** | A fixed set of 50 scripted tasks run against the fake and real model to catch regressions (including "claimed success but failed" cases). |
| **Skill health tracking** | Each skill logs success rate. A skill that keeps failing is flagged and can be repaired by the Skill Forge. |

## 5. Honest Limits

- **Model quality is the ceiling.** A 4B model on 6 GB VRAM writes simple skills reliably and complex ones poorly. The Skill Forge therefore uses templates, validates, tests, and (opt-in) can call a cloud model to draft hard skills.
- **UI automation breaks when apps update.** WhatsApp, Office ribbon, and screen-based clicks are the most fragile areas. UI Automation (UIA) is used before pixel clicking.
- **Autonomous UI control (`ui.act`) is slow and unreliable on small models.** It is capped at 10 steps, confirms HIGH-risk steps, and falls back to keyboard shortcuts first.
