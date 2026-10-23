# T.A.R.O. - User Guide & Setup Manual

**Total Autonomous Robotic Operator (T.A.R.O.)**  
*A 100% Local-First, Privacy-Preserving Autonomous Windows Desktop Assistant*

---

## 1. System Requirements

- **Operating System:** Windows 10 (Build 19041+) or Windows 11 (64-bit).
- **Python Version:** Python 3.11 or Python 3.12 (64-bit).
- **RAM:** Minimum 16 GB system memory.
- **GPU (Optional but Recommended):** NVIDIA GPU with 6 GB VRAM minimum (RTX 2060, 3060, 4060, or better). Full CPU fallback supported.
- **Local Model Engine:** [Ollama](https://ollama.com/) running locally on `http://127.0.0.1:11434`.

---

## 2. Installation from Source

### Step 1: Clone or Open Repository
```cmd
cd /d D:\T.A.R.O
```

### Step 2: Create a Clean Virtual Environment
```cmd
python -m venv venv
.\venv\Scripts\activate
```

### Step 3: Install Dependencies
```cmd
pip install --upgrade pip
pip install -r requirements.txt
```

### Step 4: Verify Local Health with `--doctor`
Run the automated diagnostics suite:
```cmd
python main.py --doctor
```
This tests:
- Python version and environment
- Ollama local endpoint connectivity
- GPU and VRAM availability (or CPU fallback)
- Audio input (microphone) and output (speakers)
- Core integrity manifests

---

## 3. Configuration

Configuration files are located in `config/`:

| File | Purpose |
| :--- | :--- |
| `config/config.yaml` | System default configuration (models, timeouts, ports). |
| `config/config.local.yaml` | Workstation-specific overrides (ignored by git). |
| `config/permissions.json` | Risk-level permissions per tool category (`allow`, `ask`, `ask_typed`, `deny`). |
| `config/skill_allowlist.json` | Allowed standard library and 3rd-party packages for dynamic skills. |

### Model Configuration Example (`config/config.yaml`)
```yaml
model:
  engine: "ollama"
  name: "taro"
  host: "http://127.0.0.1:11434"
  timeout_s: 30.0

safety:
  immutable_core: true
  max_consecutive_tool_failures: 3
  kill_switch_hotkey: "ctrl+alt+f12"

cloud:
  enabled: false  # Zero cloud dependency by default.
```

---

## 4. Running T.A.R.O.

### Interactive CLI Mode
```cmd
python main.py
```
Type prompts directly into the terminal. All tool executions and risk confirmation cards appear interactively.

### Web HUD Interface Mode
```cmd
python main.py --hud
```
Launches the dual-column glassmorphic HUD:
- **Left Panel:** Live conversation stream, reactive status orb, audio waveform visualizer.
- **Right Panel:** Tool execution telemetry, expandable logs, secret argument masking, approval cards.
- **Confirmations:** MEDIUM risk actions show One-Click Approval buttons. HIGH risk actions require typing the exact confirmation phrase.

### Emergency Kill Switch
At any time, press **`Ctrl+Alt+F12`** to trigger the global emergency kill switch. All running subprocesses are immediately terminated and tool execution is halted.

---

## 5. Self-Extension & The Skill Forge

T.A.R.O. can create its own tools without modifying core system files:
1. Ask T.A.R.O.: *"Create a skill to search my Downloads folder for duplicate files."*
2. T.A.R.O. drafts a specification in `skills/downloads_dedup/skill.json`.
3. Code is generated from validated templates (`skills/_templates/`).
4. Static AST analysis checks for security violations (no `eval`, `exec`, or writes to `core/`).
5. The skill runs in a trial sandbox for 3 test runs before graduating to registered status.

---

## 6. Troubleshooting & FAQs

### 1. Doctor reports `Ollama is not running`
- Start the Ollama desktop application or run `ollama serve` in a command prompt.
- Verify `http://127.0.0.1:11434` responds in your browser.

### 2. Windows Defender flags input libraries
- T.A.R.O. uses native Windows APIs for hotkeys and window automation.
- See `docs/security-review.md` section 2 for instructions on adding an exclusion path in Windows Defender.

### 3. Core Integrity Tamper Alert at Startup
- If you manually modified files in `core/` or `config/permissions.json`, update the manifest:
  ```cmd
  python scripts/update_manifest.py
  ```
  *(Never bypass this in production environments!)*
