# T.A.R.O. - Project Status & Roadmap

**System:** T.A.R.O. (Total Autonomous Robotic Operator)  
**Version:** 1.3.0  
**Last Updated:** 2026-10-22 17:30 IST  
**Target Platform:** Windows 10/11 (Local-First, Privacy-Preserving)  
**Test Suite Status:** **165/165 tests passing (100% Pass Rate across ALL Phases 0 through 8)**

---

## 1. Executive Summary & Architecture

T.A.R.O. is a fully autonomous, local-first Windows assistant designed for zero cloud dependency by default, strictly bounded VRAM usage (< 5.5 GB peak), robust safety controls, multi-step tool orchestration, vision and voice capabilities, autonomous skill self-extension (Skill Forge), dual-column glassmorphic HUD, custom voice expressions, automatic Ollama lifecycle management, and production-hardened Windows packaging.

### Model Configurations
- **Primary Ollama Model:** `richardyoung/qwen3-8b-abliterated:Q4_K_M` (5.0 GB)
- **Secondary Backup Model:** `nemotron-3-nano:4b` (2.8 GB)
- **Taro Custom Model:** `taro:latest` (5.0 GB)
- **Cloud API Fallback:** OpenAI / Anthropic / Gemini API (opt-in only, requires explicit flag and user key)
- **VLM Vision Model:** `moondream:latest` (1.7 GB, loaded on-demand, auto-unloaded after 30s)
- **STT Engine:** `faster-whisper base.en` (CPU-bound, always loaded)
- **TTS Engine:** `edge-tts` (online) with `pyttsx3` offline fallback
- **Token Budget:** **32,768 tokens (32k context window)** with structured prompt allocation:
  - System: 1,500 | Tools: 4,000 | Profile/Memory: 2,000 | Summary: 2,000 | Recent Turns: 20,000 | Response Reserve: 3,268

---

## 2. What Is Done (Completed Work across All Phases)

### Phase 0: Foundations ✅
- **Repository layout & virtualenv:** Python 3.11/3.12+ virtual environment (`venv/`).
- **Configuration Engine (`core/config.py`):** Pydantic-validated YAML configuration with local override support (`config/config.yaml` and `config/config.local.yaml`).
- **Structured Logging (`core/log/`):** JSON-line structured logging with automated secret masking (`API_KEY`, passwords, bearer tokens).
- **Test Harness:** Comprehensive pytest suite with Windows import guard rules preventing stdlib shadowing.

### Phase 1: Local Model Core ✅
- **Ollama Client (`core/model/ollama_client.py`):** Streaming, tool-calling schema translation, configurable timeouts, retries, fallback handling. **Updated: 32k context defaults.**
- **Model Manager (`core/model/model_manager.py`):** Strict single-large-model enforcement in VRAM, active `keep_alive` control, and background `nvidia-smi` VRAM telemetry.
- **Prompt Builder (`core/prompt_builder.py`):** Token budgeting within **32,768 tokens**, persona injection (`config/persona.md`), system clock awareness.
- **Three-Tier Memory Architecture (`core/memory/`):**
  - *Tier 1 (SQLite):* Complete turn logs, tool invocation records, rolling summaries.
  - *Tier 2 (ChromaDB):* Semantic vector memory using offline sentence transformers.
  - *Tier 3 (JSON):* Workflow definitions, user preferences, trusted action policies.
- **Rolling Summarizer (`core/summarizer.py`):** Automatically compacts conversation history every 5 turns into SQLite without blowing token budget.

### Phase 2: Orchestrator & Tool System ✅
- **Base Tools (`core/tools/base.py`):** Type-safe `BaseTool`, structured `ToolResult` (status, output, error, duration, metadata), risk classification.
- **Tool Registry (`core/tools/registry.py`):** Automatic category-based schema filtering so chat turns send minimal schemas.
- **Plan/Act Orchestrator Loop (`core/orchestrator.py`):** Up to 12 autonomous tool execution steps, deterministic status block code verification (model cannot fabricate tool success).

### Phase 3: Safety & Governance ✅
- **Risk Classifier (`core/safety/risk.py`):** Base risk + dynamic argument escalation (e.g., file writes outside workspace escalate to HIGH/CRITICAL).
- **Permission Map (`core/safety/permissions.py`):** Category-level `allow`, `ask`, and `deny` rules.
- **Confirmation Flow (`core/safety/confirmation.py`):** MEDIUM requires explicit yes/no; HIGH/CRITICAL requires exact typed phrase confirmation.
- **Audit Log (`core/safety/audit.py`):** Cryptographic SHA-256 hash-chained JSON-line audit trail with tamper detection.
- **Code Execution Sandbox (`core/safety/sandbox.py`):** Confined to `sandbox/`, 30s hard timeout, memory and process limits.
- **Global Kill Switch (`core/safety/kill_switch.py`):** Dedicated low-level thread listening for `Ctrl+Alt+F12`, tray button, or `taro kill`.
- **Registry Backup (`capabilities/files/registry_ops.py`):** Automated `.reg` backup before any registry write.
- **Untrusted Content Wrapper (`core/safety/untrusted.py`):** Taint tracking for web pages, files, and clipboard inputs.

### Phase 4: Capabilities Parity ✅
- **App Lifecycle & Process Control (`capabilities/system/apps.py`):** Launch (`app.launch`) and graceful close (`app.close`) for 30+ applications, including WhatsApp, Telegram, Opera, Chrome, Edge, Notepad, Calculator, etc., with process polling verification.
- **WhatsApp Automation (`capabilities/system/apps.py`):** Dedicated `message.whatsapp` tool automating contact chat search (e.g. "jagunu") and phone number URIs with automated typing and message dispatch.
- **Window Management (`capabilities/system/windows.py`):** Minimize, maximize, restore, close, switch windows.
- **Process Management (`capabilities/system/processes.py`):** Process listing and guarded termination.
- **File System (`capabilities/files/operations.py`):** Workspace path-guarded copy, move, rename, delete, read, write, search, undo, and dry run.
- **Web Intelligence (`capabilities/web/`):** Web search (DuckDuckGo), web page fetcher, text extraction.
- **Office Suite (`capabilities/office/`):** Excel automation (`openpyxl`), Word (`python-docx`), PowerPoint (`python-pptx`).
- **Hardware & Telemetry (`capabilities/system/`):** Volume, brightness, power control, CPU/RAM/VRAM/Disk/Network/Temp monitor.
- **Clipboard (`capabilities/system/clipboard.py`):** Safe read/write via pyperclip.
- **Reminders & Timers (`capabilities/reminders/timers.py`):** Background scheduled timers with notification callbacks.
- **Notes System (`capabilities/notes/notes.py`):** Dual storage in markdown files and ChromaDB semantic memory.

### Phase 5: Vision & Voice Pipeline ✅
- **Screen Capture (`capabilities/vision/capture.py`):** Full-screen, region, and window capture downscaled to 640x360 in-memory JPEG under 200ms with sensitive window masking.
- **OCR Engine (`capabilities/vision/ocr.py`):** Offline image-to-text extraction via Tesseract.
- **Vision Model Tool (`capabilities/vision/vlm.py`):** On-demand Ollama VLM integration with anti-hallucination validation and 30s auto-unload.
- **Camera Tool (`capabilities/vision/camera.py`):** Single-frame capture with OpenCV fallback; disabled by default until explicitly enabled.
- **STT Engine (`voice/stt.py`):** CPU-bound `faster-whisper` (`base.en` / `int8`) speech-to-text, energy-based VAD.
- **Wake Word Detector (`voice/wake_word.py`):** Lightweight energy pre-filter + keyword check for wake word "taro" (idle CPU < 4%).
- **TTS Engine (`voice/tts.py`):** Online `edge-tts` with automatic offline `pyttsx3` fallback.
- **Microphone Diagnostic Self-Test (`voice/mic_test.py`):** Real-time hardware probe reporting device name, RMS audio level, and pass/fail state.

### Phase 6: Skills & Training Pipeline ✅
- **Skill Loader (`core/skills/loader.py`):** Dynamic discovery of skills in `skills/`, schema validation, execution wrapper (`SkillToolAdapter`), enable/disable support.
- **Skill Validator (`core/skills/validator.py`):** Enforces strict snake_case naming, semantic versioning, JSON Schema input specification, risk classification, and PermissionManager integration.
- **Built-in Skills (`skills/`):** `excel_automation`, `file_organizer`, `system_info`.
- **Training Recorder (`capabilities/training/recorder.py`):** Event recording with automatic password field masking (`[MASKED_PASSWORD_FIELD]`).
- **Workflow Compiler (`capabilities/training/compiler.py`):** Groups mouse movements and keystrokes into clean `type_text` actions with target window context.
- **Workflow Replayer (`capabilities/training/replayer.py`):** Step-by-step verification before executing each recorded step; halts immediately on window mismatch.
- **Workflow Manager (`capabilities/training/manager.py`):** Full CRUD for recorded workflows with export as callable skills.

### Phase 6b: Skill Forge & Self-Extension Engine ✅
- **Tool Discovery & `find_tools` Meta-Tool (`core/discovery.py`):** Fast embedding/tag-based tool retrieval.
- **Skill Templates (`skills/_templates/`):** Production templates for `file`, `web`, `excel`, `text`, and `api`.
- **Forge Spec Writer (`core/forge/spec_writer.py`):** Drafts formal `skill.json` specifications from natural language requests.
- **Forge Generator (`core/forge/generator.py`):** Syntactically verified `execution.py` code generation with retry loops.
- **Static AST Security Checker (`core/forge/static_check.py`):** Comprehensive AST inspection blocking banned modules, banned functions, immutable paths, and dunder introspection. All 20 malicious test snippets rejected.
- **Forge Test Runner (`core/forge/test_runner.py`):** Automated sandbox dry-run execution validating newly generated skill code.
- **Skill Registrar & Approval Gate (`core/forge/registrar.py`):** Two-step human approval loop; SHA-256 manifest hash verification; initial 3 runs in `trial` mode.
- **Skill Health Monitor (`core/forge/health.py`):** Tracks consecutive failures; 3 consecutive failures trigger an automated repair offer.
- **Skill Host Subprocess (`core/forge/skill_host.py`):** Subprocess execution host sanitizing API keys and killing runaway processes on timeout.
- **MCP Client Adapter (`core/skills/mcp_client.py`):** Register external MCP servers with default MEDIUM risk.

### Phase 6c: Parity Additions ✅
- **TASK-130: Input Control (`capabilities/system/input_control.py`):** Mouse click, move, scroll, hotkeys, and gestures.
- **TASK-131: Explorer Automation (`capabilities/system/input_control.py`):** Open directory, create new folder, select all, refresh.
- **TASK-132: App Intelligence & Priority (`capabilities/system/app_intel.py`):** Enumerate installed applications, manage launch aliases, and control process priority.
- **TASK-133: UI Automation Search (`capabilities/system/ui_automation.py`):** UI control search and tree extraction.
- **TASK-134: `ui.act` Autonomous Loop (`capabilities/system/ui_automation.py`):** Bounded 10-step UI automation loop with post-step verification; halts on mismatch.
- **TASK-135: Screen Diff & Watch (`capabilities/vision/screen_watch.py`):** Region change detector alerting within 2 seconds.
- **TASK-136: Shell Templates in Sandbox (`capabilities/coding/shell_templates.py`):** Parametrized PowerShell and CMD templates executed strictly within `sandbox/` with injection sanitization.
- **TASK-137: Security Guardian (`capabilities/system/security_guardian.py`):** Background process monitor flagging temp-directory executions; quarantine requires explicit confirmation.
- **TASK-138: Notification Guardian (`capabilities/system/notification_guardian.py`):** Desktop notification inspection, draft replies; sending strictly requires confirmation.
- **TASK-139: Persistent Workflow Scheduler (`capabilities/reminders/scheduler.py`):** Schedules survive application restarts; HIGH-risk schedules strictly refused.
- **TASK-140 & 141: File Undo & Dry-Run (`capabilities/files/operations.py`):** Recovery folder undo for deleted files; preview mode for planned changes.
- **TASK-142: Model Router (`core/model/router.py`):** Local-first routing; unauthorized cloud calls thrown as `CloudBlockedError`; permitted requests logged.
- **TASK-143: Diagnostics (`main.py --doctor`):** Comprehensive diagnostic self-check.
- **TASK-144: Local Usage Analytics (`core/analytics/usage.py`):** Local execution metrics, tool counts, failure rates.
- **TASK-145: Document Q&A (`capabilities/notes/doc_qa.py`):** Document indexing and query answering strictly citing file and page.
- **TASK-146: Evaluation Harness (`tests/test_eval_harness.py`):** 50 scripted acceptance tasks testing safety, planning, anti-hallucination, and error recovery.

### Phase 7: HUD & User Experience ✅
- **PyWebView Shell & HTTP Server (`core/ws/server.py`):** Embedded UI shell serving `ui/html/taro_hud.html` from `127.0.0.1`.
- **Authenticated WebSocket Server (`core/ws/server.py`):**
  - Session token authentication with constant-time comparison (`core/ws/auth.py`).
  - Strict `Host` header (DNS rebinding protection) and local `Origin` header validation.
  - Bi-directional protocol supporting streaming chat tokens, telemetry broadcast, model status, and confirmation dialogs.
- **Glassmorphic HUD Layout (`ui/html/taro_hud.html`):** Two-column desktop layout with pulsing reactive voice orb, telemetry cards, and expandable activity log.
- **Confirmation Cards (`core/ws/protocol.py`):** Interactive confirmation requests supporting one-click approve/deny for MEDIUM risk and typed phrase confirmation for HIGH/CRITICAL risk.
- **Tool Activity Panel (`core/ws/protocol.py`):** Real-time execution logs with automated masking of sensitive arguments (`api_key`, `password`, `token`).
- **Settings Manager (`core/ws/settings_manager.py`):** Full read/write management for all HUD configuration sections with local overrides in `config/config.local.yaml`. **Updated: 32k context values.**
- **Keyboard Shortcuts & Accessibility (`core/ws/accessibility.py`):** Full WCAG AA accessibility compliance, ARIA live regions, focus indicators, and `Ctrl+Alt+F12` global kill switch.
- **Memory Viewer & Editor (`core/ws/memory_viewer.py`):** Unified viewer and deletion interface across all three memory tiers (SQLite, ChromaDB, and JSON).
- **Proactive Suggestions (`core/ws/protocol.py`):** Low-priority proactive assistant suggestions requiring user confirmation prior to execution.

### Phase 8: Hardening & Packaging ✅
- **TASK-090: Endurance & Soak Test Harness (`tests/test_soak.py`):** Multi-iteration mixed session stress test verifying peak memory remains strictly bounded under 5.5 GB.
- **TASK-091 & TASK-095: Security Review & Antivirus Compatibility (`docs/security-review.md`):** Comprehensive analysis of permissions, sandbox confinement, Windows Defender heuristics, and input-hook allowlisting guidelines.
- **TASK-092: Error Handling Audit (`tests/test_error_handling.py`):** Audited entire codebase for bare `except:` clauses (0 found); verified exact error message surfacing.
- **TASK-093: PyInstaller Build Specification (`taro.spec`, `scripts/build_package.py`):** Production Windows executable build specification and validation.
- **TASK-094: Comprehensive User Guide (`docs/USER_GUIDE.md`):** Complete installation, configuration, launch mode, and troubleshooting documentation.

---

## 3. What Was Done in Latest Sprint (v1.2.0 → v1.3.0)

### 3a. 32k Context Token Upgrade ✅
- **`config/config.yaml`:** `num_ctx` set to `32768`, `num_predict` set to `2048`.
- **Prompt Budget Allocation (`config/config.yaml`):**
  - system: 1,500 | tools: 4,000 | profile_and_memory: 2,000 | summary: 2,000 | recent_turns: 20,000 | response_reserve: 3,268 (total = 32,768)
- **`core/model/ollama_client.py`:** Default `num_ctx=32768` and `num_predict=2048` in both `chat()` and `stream_chat()`.
- **`core/prompt_builder.py`:** Docstring updated to document 32k budget allocation.
- **`core/ws/settings_manager.py`:** HUD settings report 32k context to the UI.
- **`core/discovery.py`:** Documentation updated to reference 32k budget.

### 3b. Ollama Auto-Starter & Model Activator ✅
- **New: `core/model/ollama_auto_starter.py`:**
  - `find_ollama_executable()` — Searches PATH + common Windows install locations for `ollama.exe`.
  - `is_ollama_server_active()` — Pings `http://127.0.0.1:11434/api/tags` to verify server health.
  - `start_ollama_server()` — Spawns `ollama serve` in background with `CREATE_NO_WINDOW` (no console popup).
  - `activate_model()` — Sends pre-warm generate request to load model into GPU VRAM.
  - `ensure_ollama_ready()` — Full lifecycle: check → start → wait → pre-warm.
- **`main.py` Integration:**
  - `ensure_ollama_ready()` is called **before** launching either CLI or HUD mode.
  - If Ollama fails to start, prints a warning but continues (graceful degradation).

### 3c. HUD Desktop Application Launch Mode ✅
- **New: `run_hud_app()` in `main.py`:**
  - Starts the WebSocket HUD server on `127.0.0.1:8765`.
  - Automatically opens the user's browser to `http://127.0.0.1:8765`.
  - Registers all capabilities, creates orchestrator, starts hotkey listener.
  - Clean shutdown on `Ctrl+C`: stops server, stops hotkeys, unloads models.
- **New CLI Arguments:**
  - `python main.py --hud` — Launch HUD desktop application.
  - `python main.py --app` — Alias for `--hud`.
- **Version bumped to v1.3.0** across all banners.

### 3d. Custom ElevenLabs Voice Expressions ✅
- **Voice Assets:**
  - Imported user's two ElevenLabs MP3 files into `voice/assets/expressions/`:
    - `expression_sample_1.mp3` — Ram: Slow Clear EdTech (Thoughtful)
    - `expression_sample_2.mp3` — Ram: Slow Clear EdTech (Empathetic)
- **New: `voice/expressions.py` (`ExpressionManager`):**
  - Manages vocal expression profiles with categories (thoughtful, empathetic, curious, pleased, focused).
  - Auto-imports new ElevenLabs files from user's Downloads folder.
  - Maps expressions to visual themes (badge text, color, glow effect).
- **WebSocket Integration (`core/ws/server.py`):**
  - Static route `/voice/assets` serves MP3 files.
  - New message types: `get_expressions`, `set_expression`, `play_expression`.
  - Response types: `expressions_list`, `expression_changed`, `play_voice_expression`.
- **HUD Integration (`ui/html/taro_hud.html`):**
  - Expression Badge (`#expressionBadge`) shows current mood (💡 Thoughtful, ✨ Empathetic).
  - Dropdown selector (`#voiceExpSelect`) to switch expressions.
  - Play button (`#playVoiceExpBtn`) triggers MP3 playback with orb visual sync.
  - Audio playback sets orb to "speaking" state with aura level 0.75, reverts on end.

---

## 4. What Is Being Done Right Now (Current State)

1. **All 165 tests passing (100% Pass Rate).**
2. **All tasks in `docs/TASKS.md` from Phase 0 to Phase 8 are marked ✅.**
3. **v1.3.0 release candidate is functionally complete.**

---

## 5. What Should Be Done Next (Future Roadmap: Phase 9+)

With all core development, HUD, capabilities parity, voice expressions, and hardening phases complete, future enhancements can focus on:

- **TASK-100:** Natural-language workflow creation building directly on the Forge.
- **TASK-101:** Advanced cron-like visual scheduling in the HUD.
- **TASK-102:** Optional containerized isolation (WSL or Windows Sandbox container user).
- **TASK-103:** Benchmark-driven local speech model upgrades.
- **TASK-104:** External Plugin SDK distribution packaging.
- **TASK-105:** PyWebView native window (replacing browser tab with frameless window).
- **TASK-106:** Real-time voice activity detection with level-driven orb animations during STT.
- **TASK-107:** Additional voice expression profiles (e.g., from user recordings).

---

## 6. Installed Ollama Models (Host Machine)

| Model | Size | Role |
| :--- | :--- | :--- |
| `taro:latest` | 5.0 GB | Custom fine-tuned model |
| `richardyoung/qwen3-8b-abliterated:Q4_K_M` | 5.0 GB | **Primary Chat Model** |
| `nemotron-3-nano:4b` | 2.8 GB | Backup / fallback model |
| `moondream:latest` | 1.7 GB | Vision model (on-demand) |

---

## 7. Quick Reference Commands

### Launch HUD Desktop App (Recommended)
```powershell
.\venv\Scripts\python main.py --hud
```

### Launch Interactive CLI
```powershell
.\venv\Scripts\python main.py
```

### Run Full Test Suite
```powershell
.\venv\Scripts\pytest -q
```

### Run 50-Task Evaluation Harness
```powershell
.\venv\Scripts\pytest tests/test_eval_harness.py -v
```

### Run Diagnostics & Doctor
```powershell
.\venv\Scripts\python main.py --doctor
```

### Run Packaging Spec Validation
```powershell
.\venv\Scripts\python scripts/build_package.py --dry-run
```

### Trigger Emergency Kill Switch
```powershell
.\venv\Scripts\python main.py kill
```

---

## 8. Key Files Modified in v1.3.0

| File | Change |
| :--- | :--- |
| `config/config.yaml` | 32k context, 2048 predict, prompt budget allocation |
| `core/model/ollama_client.py` | Default `num_ctx=32768`, `num_predict=2048` |
| `core/prompt_builder.py` | Docstring updated to 32k budget breakdown |
| `core/ws/settings_manager.py` | HUD settings report 32k context |
| `core/discovery.py` | Documentation references 32k budget |
| `core/model/ollama_auto_starter.py` | **New:** Ollama lifecycle manager |
| `voice/expressions.py` | **New:** Expression manager |
| `voice/assets/expressions/` | Two ElevenLabs MP3 voice files |
| `core/ws/server.py` | Expression handlers + static voice route |
| `ui/html/taro_hud.html` | Expression badge, play button, dropdown, audio playback |
| `main.py` | Ollama auto-start, `--hud`/`--app` mode, v1.3.0 banners |
| `PROJECT_STATUS.md` | This file — comprehensive status update |
