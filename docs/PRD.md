# T.A.R.O. - Product Requirements Document

**Version:** 1.2.0 (Draft)
**Owner:** Somesh
**Status:** Planning

---

## 1. Vision

T.A.R.O. (Tactical Augmentation & Resource Orchestrator) is a single-agent, local-first AI operating assistant for Windows. It delivers the full feature set of J.A.R.V.I.E.S. V11 (voice, vision, automation, memory, skills, training mode, safety gates) through one orchestrator that plans and executes multiple tasks itself. There are no sub-agents. Every capability is a tool or skill that the one orchestrator can call.

## 2. Problem

J.A.R.V.I.E.S. splits work across five agents that share one model. This causes routing errors, duplicated prompts, hard-to-trace failures, and fragile keyword shortcuts. T.A.R.O. replaces agent routing with one reasoning loop that chooses tools through native tool-calling.

## 3. Target User and Hardware

- **User:** Somesh (power user, developer, Windows).
- **Hardware:** Ryzen 5 6600H, RTX 4050 Laptop GPU 6 GB VRAM, 16 GB RAM, 512 GB SSD.
- **Platform:** Windows 10/11 first-class. Linux/macOS are out of scope for v1.

## 4. Goals

| ID | Goal | Measure |
| :--- | :--- | :--- |
| G-1 | Feature parity with J.A.R.V.I.E.S. V11 core features | Every item in Section 6 marked done |
| G-2 | Single orchestrator, no sub-agent routing | 0 agent-to-agent hops in the request path |
| G-3 | Stay within 6 GB VRAM | Peak VRAM under 5.5 GB during chat; vision model unloaded after use |
| G-4 | Never claim an action succeeded without a verified tool result | 100% of success claims backed by a tool result in the audit log |
| G-5 | Safe execution | Every HIGH or CRITICAL action requires user confirmation |

## 5. Non-Goals (v1)

- Multi-user, cloud sync, mobile companion, marketplace (deferred to Phase 9+).
- Docker deployment (deferred).
- Self-modification of the safety layer. This is permanently out of scope.
- Linux or macOS support.
- Training a custom model. T.A.R.O. uses existing open-weight models through Ollama.
- Unaligned or "no safety filter" model behaviour. Safety is enforced by the permission and confirmation system, not by prompt tricks.

## 6. Functional Requirements

Each requirement maps to a JARVIS V11 feature that T.A.R.O. must reproduce.

### FR-1 Orchestrator (replaces 5-agent system)
- Single loop: understand, plan, call tools, verify results, respond.
- Multi-task handling: a request may contain several sub-tasks. The orchestrator keeps a task list and runs them in order, or in parallel when they are independent (for example, a web search while a file is being written).
- Step limit per request (default 12) and per-tool timeout (default 30 s).
- Time-aware greeting (morning, afternoon, evening, night) from the system clock.

### FR-2 Chat Interface
- Text input in the HUD and in the terminal.
- Token streaming to the UI.
- Conversation history, search, and clear (Ctrl+L).
- Command history (Up/Down arrows).

### FR-3 Voice
- Wake word "taro" (replaces "jarvis") using a dedicated keyword detector (openWakeWord custom model or Porcupine), with push-to-talk and a HUD mic button as always-available fallbacks.
- STT: faster-whisper `base.en` or `small.en` on CPU. Google STT as an online fallback only with consent.
- TTS: edge-tts (online) with pyttsx3 (offline) fallback.
- Continuous listening mode, push-to-talk option, and a microphone self-test.
- Audio playback through a single worker thread with a queue.

### FR-4 Application and Window Control
- Launch applications from a configurable app map (30+ common Windows apps, editable in config).
- Verify launches with process polling. Report "Failed" with the exact error when the process does not appear.
- Minimize, maximize, restore, close, and switch windows.
- Process listing and termination (with HIGH risk confirmation).

### FR-5 File System Operations
- Copy, move, rename, delete, search, read, and write files.
- Delete and overwrite are HIGH risk and need confirmation.
- Default writable root: `%USERPROFILE%\TARO\workspace\`. Other locations need explicit permission.

### FR-6 Web and Browser Automation
- Web search (DuckDuckGo or a configured search API) and page fetch.
- Browser control through Playwright, and through Chrome DevTools Protocol when attaching to an open browser.
- Open URLs, read page text, click, type, and extract content.

### FR-7 Office and Spreadsheet Automation
- Excel automation through openpyxl (files) and pywin32 (live Excel instances).
- Word and PowerPoint basics through python-docx and python-pptx.
- Excel automation is one of the built-in skills (see FR-13).

### FR-8 Screen Analysis and OCR
- Capture full screen, a region, or a window.
- Downscale to 640x360 (or a configured size), JPEG quality 75.
- OCR through Tesseract (pytesseract), used first because it is cheap.
- Vision description through a small vision-language model, loaded on demand and unloaded after use.
- Anti-hallucination: the vision prompt must only describe visible elements. Output that is empty, too short, or uncertain is reported as "unclear", not guessed.
- Captured frames are never written to disk unless the user asks. They are cleared from memory after analysis.

### FR-9 Camera Analysis
- Live preview in the HUD (WebRTC through PyWebView, OpenCV fallback).
- Single-frame analysis on request. The user must enable the camera. Camera is OFF by default.
- Same anti-hallucination rules as FR-8.

### FR-10 Code Generation and Sandboxed Execution
- Generate Python, PowerShell, and batch scripts on request.
- Execute only inside `%USERPROFILE%\TARO\sandbox\` with a timeout and captured stdout/stderr.
- Show the script and ask for confirmation before the first run of any script (HIGH risk).

### FR-11 Image Generation (cloud, opt-in)
- Gemini image generation or another configured cloud provider.
- Disabled until the user sets an API key and enables cloud use per session.
- Prompts and outputs are logged locally only.

### FR-12 Training Mode
- Record mouse and keyboard events (pynput) with an explicit start and stop command and a visible recording indicator.
- Pause automatically on password fields and never store those keystrokes.
- Compile recordings into a JSON workflow: remove duplicate moves, group keystrokes, and add window context.
- Replay a workflow with a per-step verification (window title or screen check). Stop on mismatch.
- Manage workflows: list, rename, delete, and view success rate.

### FR-13 Skills Framework
- Each skill is a folder with `SKILL.md` (description and usage), `skill.json` (schema for inputs and outputs), and `execution.py` (logic).
- Skills are discovered at startup and can be enabled or disabled in config.
- The orchestrator sees skills as tools with JSON schemas. There is no keyword-based forced invocation.
- Built-in skills at launch: Excel, file organizer, system info, clipboard, screenshot, web research, note taking, reminder, timer, workflow runner.
- User-added skills follow the same format and pass the validator (FR-13a).

#### FR-13a Skill Validator
- Checks the schema, required fields, risk level, and declared permissions before a skill loads.

### FR-14 Hardware Control
- Display brightness, audio volume and mute, media keys, and power actions (sleep, lock, shutdown with confirmation).
- Hardware stats (CPU, RAM, GPU, VRAM, disk, network, temperature where available) for the HUD.

### FR-15 Memory
- Tier 1, short-term: SQLite conversation log.
- Tier 2, long-term semantic: ChromaDB for facts, preferences, and notes.
- Tier 3, procedural: JSON for workflows, action log, and permission decisions.
- User profile file (`profile.md`) loaded every session.
- Context summarization every 5 turns to keep the prompt inside 4096 tokens.

### FR-16 Intent Parsing and Verification
- The model returns a structured intent for every request: intent, parameters, confidence (0.0 to 1.0), and risk (SAFE, LOW, MEDIUM, HIGH, CRITICAL).
- SAFE and LOW with confidence >= 0.8 execute automatically.
- MEDIUM asks for a yes/no confirmation.
- HIGH and CRITICAL require typed or spoken confirmation of the exact action.
- Voice and text confirmations are both accepted.

### FR-17 Permissions and Security
- Permission levels per tool category, stored in `config/permissions.json`.
- Trusted-action list: the user can approve a specific action pattern once ("always allow opening Chrome"). Approvals can be revoked in the HUD.
- Audit trail: every tool call, its arguments (with secrets redacted), result, and user approval, written to `logs/audit/`.
- Emergency kill switch: Ctrl+Alt+F12 stops all running tools and the model.
- Admin rights are not required by default. Actions that need admin (some registry or service changes) prompt for UAC elevation separately.
- Registry writes always create a backup first.

### FR-18 Proactive Suggestions
- Suggestions are low-priority, shown in the HUD, and never executed without confirmation.
- Can be disabled.

### FR-19 HUD (PyWebView)
- Single-agent layout: status bar, hardware diagnostics, conversation, tool activity, input bar.
- Dark theme by default. Light theme optional.
- Real-time updates over a local WebSocket.


### FR-20 Skill Forge (Self-Extension)
- When the user asks for a capability T.A.R.O. does not have, or says "create a skill that...", T.A.R.O. designs, tests, and registers a new skill. Full design in SELF_EXTENSION.md.
- Two approvals by default: the spec and the final code with test results.
- Generated code passes a static check and sandbox tests before it can be registered.
- T.A.R.O. can never edit its own safety layer, permissions, allowlist, or audit log.
- New skills start in `trial` state (confirmation on the first 3 uses).
- Supports adding tools without code: MCP servers, workflow skills, prompt skills.

### FR-34 Untrusted Content Handling
- Content from the web, files, OCR, notifications, and tool output is treated as data. See ARCHITECTURE section 23. Actions after such content always need confirmation at MEDIUM risk and above.

### FR-35 Local Interface Security
- The HUD and WebSocket accept only local, token-authenticated, same-origin connections. See ARCHITECTURE section 24.

### FR-21 Tool Discovery
- A `find_tools` meta-tool searches tool and skill descriptions and loads matching schemas into the next model call. This keeps the context small while the tool count grows.

### FR-22 Application Intelligence
- Background app and window monitor, application discovery (Start Menu, registry), aliases, UI Automation tree extraction, element search by name, type, or automation ID, window text extraction.

### FR-23 Autonomous UI Action Loop (`ui.act`)
- Observe, orient, decide, execute, verify loop for tasks on apps with no API.
- Prefers keyboard shortcuts and UI Automation over pixel clicks.
- Max 10 steps. HIGH-risk steps need confirmation. Stops on verification mismatch.

### FR-24 Keyboard, Mouse, Hotkeys, Gestures
- Key press, hotkeys, typing, click, drag, scroll. Register user hotkeys. Mouse gestures (swipe, circle, zoom).

### FR-25 Shell Templates
- Save and reuse PowerShell and CMD templates with parameters. Execution still goes through the risk gate and sandbox rules.

### FR-26 Security Guardian (optional service, off by default)
- Scans running processes every 60 s for suspicious behaviour (execution from temp folders, abnormal CPU or memory).
- Uses Windows Defender for scanning. Never quarantines or terminates without user confirmation. Logs every incident.

### FR-27 Notification Guardian (optional service, off by default)
- Reads Windows notifications from selected apps, summarizes them, and drafts replies.
- Sends nothing without confirmation. Per-app opt-in.
- **Experimental.** Windows notification access (`UserNotificationListener`) can require app package identity and may not work from a plain Python process. If it is unavailable, the service reports "unsupported on this setup" and stays off. It never fails silently.

### FR-28 Scheduler
- Cron-like scheduling of workflows, reminders, and skills. Survives restarts. Scheduled actions use the same risk gate; HIGH-risk scheduled actions are not allowed to run unattended.

### FR-29 Undo and Dry Run
- File deletes go to a recovery folder first (kept 30 days). `undo` restores the last N actions.
- Dry-run mode for file and system tools shows what would change.

### FR-30 MCP Client
- Connect external MCP tool servers. Their tools pass the same risk gate and start at MEDIUM risk.

### FR-31 Model Router
- Local model by default. Cloud providers (Gemini, OpenAI, Groq, Anthropic) are opt-in per provider and per request. Every cloud call is logged with the data sent.

### FR-32 Diagnostics and Analytics
- `taro.doctor` checks Ollama, models, VRAM, mic, camera, permissions, and prints fixes.
- Local-only usage analytics: tool frequency, success rate, timing, and failures.

### FR-33 Local Document Q&A
- Index folders (PDF, DOCX, TXT, MD) into ChromaDB and answer from them with source file and page.

## 7. Non-Functional Requirements

| ID | Requirement | Target |
| :--- | :--- | :--- |
| NFR-1 | Generation speed | 15 tokens/s minimum on 6 GB VRAM (benchmark decides the model; see ARCHITECTURE) |
| NFR-2 | First token latency | under 2 s for a simple chat turn |
| NFR-3 | Screen capture to analysis | under 2 s with OCR, under 4 s with vision model |
| NFR-4 | Voice command to action | under 3 s for SAFE commands |
| NFR-5 | VRAM | under 5.5 GB peak during chat, 1.5 GB free for OS |
| NFR-6 | Idle CPU | under 4% |
| NFR-7 | Reliability | Tool failures are reported with the exact error; no silent failure |
| NFR-8 | Privacy | Local-only by default. No outbound calls without an enabled cloud feature |
| NFR-9 | Maintainability | Modules under 500 lines each. No single file over 800 lines |

## 8. Constraints

- 6 GB VRAM means one large model at a time. Vision and STT must not overlap with a large chat model.
- Python 3.12+. Windows-only APIs (pywin32, pywinauto, pynput) are isolated behind an adapter layer.
- No hardcoded keys. Secrets are read from `.env`.

## 9. Success Criteria

- All Section 6 requirements pass their acceptance tests (see TASKS.md).
- A user can complete these end-to-end by voice: "taro open excel, make a sheet with three columns, save it to my workspace" with the save step confirmed.
- No VRAM out-of-memory errors in a 1-hour mixed test session.

## 10. Open Decisions

| ID | Question | Default until decided |
| :--- | :--- | :--- |
| D-1 | Main model: Qwen3 4B vs Qwen3 8B (partial offload) | Qwen3 4B, benchmark 8B in TASK-011 |
| D-2 | Vision model: moondream vs Qwen2.5-VL 3B | moondream (smallest), benchmark in TASK-021 |
| D-3 | Wake word: "taro" only, or also "jarvis" | "taro" only |
| D-4 | Keep WhatsApp automation (fragile UI automation) | Deferred to Phase 8 |
| D-5 | Skill Forge approval mode: `ask` or `trusted-low` | `ask` |
| D-6 | Allow an opt-in cloud model to draft hard skills | Off |
