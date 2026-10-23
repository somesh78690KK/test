# T.A.R.O. - Setup Guide

**Version:** 1.2.0 (Draft)

Target machine: Windows 10 (2004+) or 11, Ryzen 5 6600H, RTX 4050 Laptop 6 GB, 16 GB RAM.
Check each step with the verification line. `python main.py --doctor --prereqs` (TASK-006) automates these checks.

Model tags and package versions change over time. Confirm a tag exists (`ollama list`, ollama.com library) before relying on it, and record what you actually installed in `docs/benchmarks.md`.

---

## 1. Prerequisites

| Item | Why | Install | Verify |
| :--- | :--- | :--- | :--- |
| NVIDIA driver (current Game Ready or Studio) | GPU inference | nvidia.com drivers | `nvidia-smi` shows the RTX 4050 and 6 GB |
| Python 3.12 (64-bit) | Runtime | python.org installer, tick "Add to PATH" | `python --version` shows 3.12.x |
| Git | Source control | git-scm.com | `git --version` |
| Ollama for Windows | Local models | ollama.com | `ollama --version` |
| Tesseract OCR (Windows build) | `screen.ocr` | UB Mannheim installer; add install folder to PATH | `tesseract --version` |
| Microsoft Edge WebView2 Runtime | PyWebView window and camera preview | Included on Windows 11; otherwise Microsoft's evergreen installer | HUD window opens |
| Microsoft C++ Build Tools | Only if a package has no prebuilt wheel | Visual Studio Build Tools | Needed only if `pip install` reports a compiler error |

## 2. Ollama Environment Variables

Set these as user environment variables, then restart Ollama (quit from the tray icon and start again).

| Variable | Value | Reason |
| :--- | :--- | :--- |
| `OLLAMA_HOST` | `127.0.0.1:11434` | Never expose the model server to the network |
| `OLLAMA_MAX_LOADED_MODELS` | `1` | Prevents chat and vision models sitting in VRAM together |
| `OLLAMA_NUM_PARALLEL` | `1` | Parallel requests multiply the context memory |
| `OLLAMA_KEEP_ALIVE` | `10m` | Unload when idle |
| `OLLAMA_FLASH_ATTENTION` | `1` (optional) | Lower memory use; keep only if the benchmark shows no problems |
| `OLLAMA_KV_CACHE_TYPE` | `q8_0` (optional, needs flash attention) | Smaller KV cache; keep only if the benchmark shows no quality loss |

Verify: `ollama ps` shows at most one loaded model at a time during testing.

## 3. Models

```bash
ollama pull qwen3:4b
ollama pull moondream
```

If a tag is not found, search the Ollama library for the current name. `qwen3:8b` is the benchmark alternative (TASK-011).

Create the T.A.R.O. model from `config/Modelfile`:

```dockerfile
FROM qwen3:4b
PARAMETER num_ctx 4096
PARAMETER num_predict 1024
PARAMETER temperature 0.3
PARAMETER top_p 0.9
```

The persona and rules are **not** put in the Modelfile. `core/prompt_builder.py` builds them each turn from `config/persona.md`, so they can change without rebuilding the model.

```bash
ollama create taro -f config/Modelfile
ollama run taro "Reply with the single word OK."
```

Verify: the reply is OK and `nvidia-smi` shows VRAM use under 5.5 GB.

## 4. Project Environment

```bash
git clone <your-repo-url> TARO
cd TARO
python -m venv venv
venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
playwright install chromium
```

Package notes (check each against the version you install):

| Package | Note |
| :--- | :--- |
| `faster-whisper` | CPU speech-to-text. Uses CTranslate2. No PyTorch needed |
| `webrtcvad-wheels` | Use this instead of `webrtcvad`. It ships Windows wheels and avoids compiler errors |
| `openwakeword` | Wake word. A custom "taro" model must be trained or generated and saved in `models/` |
| `pywebview` | Needs WebView2 |
| `chromadb` | Embedding model must be bundled locally (MEMORY section 12) |
| `pynput`, `pywin32`, `pywinauto` | Only imported inside `winapi/` |
| `mss` | Screen capture |
| `pytesseract` | Needs the Tesseract binary from section 1 |

## 5. Configuration

```bash
copy .env.example .env
copy config\config.yaml config\config.local.yaml
```

- Put API keys only in `.env`. Leave cloud providers disabled until needed.
- Edit `config\config.local.yaml` for machine settings (paths, `capture_exclude_titles`, wake word on or off).
- Edit `config\skill_allowlist.json` yourself if you want generated skills to use more libraries.

## 6. One-Time Protection Step (needs admin once)

The installer script sets read-only permissions for your normal Windows user on `core\` and `config\permissions.json`, and writes a SHA-256 manifest of protected files (SELF_EXTENSION section 4). Run:

```bash
scripts\protect_install.bat
```

T.A.R.O. itself never runs as administrator.

## 7. First Run Checklist

1. `python main.py --doctor` shows all green or lists exact fixes.
2. Say or type: "What time is it?" Confirm a reply, a status block, and one audit line in `logs\audit\`.
3. Type: "Open Notepad." Confirm the app opens and the status block says OK.
4. Type: "Delete the file test.txt in workspace." Confirm a confirmation card appears (HIGH risk).
5. Press the HUD kill button during a long task. Confirm the task stops.
6. Disable the network adapter and ask a memory question. Confirm memory search still works.
7. Open a browser and try to connect to the T.A.R.O. port without the token. Confirm it is refused.

## 8. Updating

- Update Ollama, models, and Python packages one at a time. After each, run `python main.py --doctor` and the evaluation harness (TASK-146).
- Pin tested package versions in `requirements.txt`. Do not use unpinned installs for the build.
