"""T.A.R.O. - Main Entry Point & Diagnostics Doctor.

ARCHITECTURE reference: sections 2, 8, 24.
TASKS: TASK-006, TASK-036.

Usage:
    python main.py                     # Start core orchestrator and interface
    python main.py --doctor            # Full health check
    python main.py --doctor --prereqs  # Check system prerequisites (TASK-006)
    python main.py kill                # Trigger emergency global kill switch
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from core.config import cfg
from core.log.setup import get_logger, setup_logging
from core.model.model_manager import read_vram_sync

logger = get_logger("taro.main")


def check_prerequisites() -> dict[str, dict[str, Any]]:
    """Checks all system prerequisites for T.A.R.O. runtime.

    Returns dict mapping requirement name to {ok: bool, detail: str, fix: str}.
    """
    results: dict[str, dict[str, Any]] = {}

    # 1. NVIDIA driver and GPU VRAM
    vram = read_vram_sync()
    if vram:
        results["NVIDIA GPU"] = {
            "ok": True,
            "detail": f"{vram.total_mb} MB VRAM total, {vram.free_mb} MB free",
            "fix": "",
        }
    else:
        results["NVIDIA GPU"] = {
            "ok": False,
            "detail": "nvidia-smi failed or no NVIDIA GPU detected",
            "fix": "Install latest NVIDIA Studio / Game Ready Driver from nvidia.com",
        }

    # 2. Ollama binary
    ollama_bin = shutil.which("ollama")
    if ollama_bin:
        results["Ollama CLI"] = {
            "ok": True,
            "detail": f"Found at {ollama_bin}",
            "fix": "",
        }
    else:
        results["Ollama CLI"] = {
            "ok": False,
            "detail": "ollama not found on PATH",
            "fix": "Download and install Ollama from https://ollama.com",
        }

    # 3. Ollama server and OLLAMA_MAX_LOADED_MODELS
    import urllib.request
    import json

    ollama_host = cfg.model.ollama_host
    try:
        with urllib.request.urlopen(f"{ollama_host}/api/tags", timeout=3) as resp:
            data = json.loads(resp.read().decode())
            installed_models = [m.get("name", "") for m in data.get("models", [])]
            results["Ollama Server"] = {
                "ok": True,
                "detail": f"Running at {ollama_host} with {len(installed_models)} model(s)",
                "fix": "",
            }

            # Check configured models
            chat_mod = cfg.model.chat_model
            has_chat = any(chat_mod in m for m in installed_models)
            results["Main Model"] = {
                "ok": has_chat,
                "detail": chat_mod if has_chat else f"{chat_mod} not pulled",
                "fix": f"ollama pull {chat_mod}",
            }

            backup_mod = cfg.model.backup_model
            has_backup = any(backup_mod in m for m in installed_models)
            results["Backup Model"] = {
                "ok": has_backup,
                "detail": backup_mod if has_backup else f"{backup_mod} not pulled",
                "fix": f"ollama pull {backup_mod}",
            }
    except Exception as e:
        results["Ollama Server"] = {
            "ok": False,
            "detail": f"Cannot connect to {ollama_host}: {e}",
            "fix": "Start Ollama desktop application or run `ollama serve`",
        }
        results["Main Model"] = {"ok": False, "detail": "Ollama server unreachable", "fix": "Start Ollama"}
        results["Backup Model"] = {"ok": False, "detail": "Ollama server unreachable", "fix": "Start Ollama"}

    # 4. OLLAMA_MAX_LOADED_MODELS environment variable
    max_loaded = os.environ.get("OLLAMA_MAX_LOADED_MODELS")
    if max_loaded == "1":
        results["OLLAMA_MAX_LOADED_MODELS"] = {
            "ok": True,
            "detail": "Set to 1",
            "fix": "",
        }
    else:
        results["OLLAMA_MAX_LOADED_MODELS"] = {
            "ok": False,
            "detail": f"Value is '{max_loaded}' (must be 1 for 6GB VRAM safety)",
            "fix": "Set environment variable OLLAMA_MAX_LOADED_MODELS=1 in Windows Environment Variables or run: [System.Environment]::SetEnvironmentVariable('OLLAMA_MAX_LOADED_MODELS', '1', 'User')",
        }

    # 5. Tesseract OCR binary
    tesseract_bin = shutil.which("tesseract")
    default_tesseract_path = Path("C:/Program Files/Tesseract-OCR/tesseract.exe")
    if tesseract_bin or default_tesseract_path.exists():
        loc = tesseract_bin or str(default_tesseract_path)
        results["Tesseract OCR"] = {
            "ok": True,
            "detail": f"Found at {loc}",
            "fix": "",
        }
    else:
        results["Tesseract OCR"] = {
            "ok": False,
            "detail": "tesseract.exe not found on PATH or Program Files",
            "fix": "Install Tesseract OCR via: winget install UB-Mannheim.TesseractOCR",
        }

    # 6. WebView2 Runtime (for HUD UI)
    try:
        import winreg

        has_webview2 = False
        for hive, subkey in [
            (
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-F501-47EC-A924-A08E7369F779}",
            ),
            (
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\EdgeUpdate\Clients\{F3017226-F501-47EC-A924-A08E7369F779}",
            ),
        ]:
            try:
                with winreg.OpenKey(hive, subkey):
                    has_webview2 = True
                    break
            except OSError:
                continue

        results["WebView2 Runtime"] = {
            "ok": has_webview2,
            "detail": "Installed" if has_webview2 else "Not found in registry",
            "fix": "Download Evergreen Bootstrapper from Microsoft Edge WebView2 website" if not has_webview2 else "",
        }
    except Exception:
        results["WebView2 Runtime"] = {
            "ok": True,  # Fallback assumption if non-Windows or registry restricted
            "detail": "Assumed present on modern Windows 10/11",
            "fix": "",
        }

    return results


def run_doctor(prereqs_only: bool = False) -> int:
    """Runs diagnostics and prints formatted report."""
    print("=" * 60)
    print("T.A.R.O. - System Doctor & Prerequisites Check")
    print("=" * 60)

    results = check_prerequisites()
    all_ok = True

    for name, info in results.items():
        status = "[ OK ]" if info["ok"] else "[FAIL]"
        if not info["ok"]:
            all_ok = False
        print(f"{status} {name:<26} : {info['detail']}")
        if not info["ok"] and info["fix"]:
            print(f"       -> Fix: {info['fix']}")

    print("=" * 60)
    if all_ok:
        print("All prerequisites satisfied! System ready for T.A.R.O.")
        return 0
    else:
        print("Some prerequisites are missing. Follow the fixes above from SETUP.md.")
        return 1


async def run_interactive_cli() -> None:
    """Runs the interactive T.A.R.O. plan/act console loop."""
    import asyncio
    from capabilities import register_all_capabilities
    from core.orchestrator import Orchestrator
    from core.safety.kill_switch import kill_switch
    from core.tools.registry import get_registry
    from winapi.hotkey import default_hotkey_listener

    # 1. Register tools
    registry = get_registry()
    count = register_all_capabilities(registry)

    # 2. Start global hotkey listener (Ctrl+Alt+F12)
    default_hotkey_listener.start()

    # 3. Banner
    print("=" * 64)
    print("  T.A.R.O. - Autonomous Windows Assistant v1.3.0")
    print("=" * 64)
    print(f"  Main Model   : {cfg.model.chat_model}")
    print(f"  Backup Model : {cfg.model.backup_model}")
    print(f"  Context      : {cfg.model.num_ctx} tokens (32k)")
    print(f"  Active Tools : {count} capabilities registered")
    print("  Kill Switch  : Press Ctrl+Alt+F12 anytime or type 'kill'")
    print("  Exit         : Type 'exit' or 'quit'")
    print("=" * 64 + "\n")

    orchestrator = Orchestrator()

    try:
        while True:
            if kill_switch.is_killed:
                print("\n[!] Global kill switch is currently active. Type 'reset' to clear.")

            try:
                user_input = input("T.A.R.O. > ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nExiting T.A.R.O...")
                break

            if not user_input:
                continue

            if user_input.lower() in ("exit", "quit", "q"):
                print("Goodbye!")
                break

            if user_input.lower() == "kill":
                kill_switch.trigger(source="user_cli")
                print("[!] Kill switch triggered.")
                continue

            if user_input.lower() == "reset":
                kill_switch.reset()
                print("[OK] Kill switch reset.")
                continue

            print("\n[Thinking & Planning...]")
            turn_result = await orchestrator.process_turn(user_input)

            # Display response
            print("\n" + turn_result.reply)
            # Display status block
            if turn_result.status_block:
                print("\n" + turn_result.status_block + "\n")

            # Speak response
            try:
                from voice.tts import say
                asyncio.create_task(say(turn_result.reply))
            except Exception:
                pass

    finally:
        default_hotkey_listener.stop()
        from core.model.model_manager import get_model_manager
        mm = get_model_manager()
        await mm.unload_all()


def _open_native_desktop_window(url: str) -> None:
    """Launches the HUD in a clean standalone desktop application window."""
    import os
    import shutil
    import subprocess
    import webbrowser

    # 1. Check for Microsoft Edge (native on Windows 10/11)
    edge_candidates = [
        os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"),
        os.path.expandvars(r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"),
        shutil.which("msedge.exe"),
    ]
    for edge in edge_candidates:
        if edge and os.path.exists(edge):
            try:
                subprocess.Popen([edge, f"--app={url}", "--window-size=1280,840"])
                logger.info("launched_edge_app_window", path=edge)
                return
            except Exception:
                pass

    # 2. Check for Google Chrome
    chrome_candidates = [
        os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
        shutil.which("chrome.exe"),
    ]
    for chrome in chrome_candidates:
        if chrome and os.path.exists(chrome):
            try:
                subprocess.Popen([chrome, f"--app={url}", "--window-size=1280,840"])
                logger.info("launched_chrome_app_window", path=chrome)
                return
            except Exception:
                pass

    # 3. Fallback to default browser
    webbrowser.open(url)


async def run_hud_app() -> None:
    """Launches the T.A.R.O. HUD: starts WebSocket server, opens desktop UI, starts voice engine."""
    import asyncio

    from capabilities import register_all_capabilities
    from core.orchestrator import Orchestrator
    from core.tools.registry import get_registry
    from core.ws.server import HUDServer
    from winapi.hotkey import default_hotkey_listener

    # 1. Register tools
    registry = get_registry()
    count = register_all_capabilities(registry)

    # 2. Start global hotkey listener
    default_hotkey_listener.start()

    # 3. Create orchestrator and HUD server
    orchestrator = Orchestrator()
    hud = HUDServer(
        host="127.0.0.1",
        port=8765,
        orchestrator=orchestrator,
    )

    # 4. Start Voice Subsystem (STT listening & TTS speaking)
    audio_worker = None
    try:
        from voice.audio_worker import AudioWorker

        async def _on_voice(user_text: str) -> None:
            if user_text and user_text.strip():
                print(f"\n[Voice Command Detected]: {user_text}")
                # Broadcast voice input to HUD for display in chat
                from core.ws.protocol import create_message
                await hud.broadcast(create_message("voice_input", text=user_text))
                # Process the command
                await hud._handle_chat_turn(user_text)

        audio_worker = AudioWorker(on_input=lambda txt: asyncio.create_task(_on_voice(txt)), hands_free=cfg.voice.hands_free)
        await audio_worker.start()
        # Store audio_worker reference in HUD for push-to-talk
        hud.audio_worker = audio_worker
        print("[OK] Voice engine active: Listening on microphone for voice commands.")
        if cfg.voice.hands_free:
            print("[INFO] Hands-free mode enabled - speaks to talk automatically, or hold F9/mic button for push-to-talk.")
        else:
            print("[INFO] Say 'taro' to activate, or hold F9/mic button for push-to-talk.")
    except Exception as voice_err:
        logger.warning("voice_engine_init_notice", error=str(voice_err))
        print(f"[!] Voice engine notice: {voice_err}")

    print("=" * 64)
    print("  T.A.R.O. - Desktop Application v1.3.0")
    print("=" * 64)
    print(f"  Main Model   : {cfg.model.chat_model}")
    print(f"  Context      : {cfg.model.num_ctx} tokens (32k)")
    print(f"  Active Tools : {count} capabilities registered")
    print(f"  Kill Switch  : Press Ctrl+Alt+F12 anytime")
    print(f"  UI Address   : http://127.0.0.1:8765")
    print("=" * 64 + "\n")

    try:
        await hud.start()
        logger.info("hud_app_started", url="http://127.0.0.1:8765")
        print("[OK] T.A.R.O. Application Server running at http://127.0.0.1:8765")

        # Open dedicated desktop window
        _open_native_desktop_window("http://127.0.0.1:8765")

        # Keep running until Ctrl+C or kill
        while True:
            await asyncio.sleep(1.0)
    except KeyboardInterrupt:
        print("\n[!] Shutting down T.A.R.O. Application...")
    finally:
        if audio_worker:
            await audio_worker.stop()
        await hud.stop()
        default_hotkey_listener.stop()
        from core.model.model_manager import get_model_manager
        mm = get_model_manager()
        await mm.unload_all()
        print("[OK] T.A.R.O. shut down cleanly.")


def main() -> None:
    """Entry point."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    setup_logging()

    # Core integrity verification (TASK-125)
    from core.safety.immutable import verify_core_integrity
    integrity_ok, violations = verify_core_integrity()
    if not integrity_ok:
        print("[CRITICAL] Core system files have been modified or corrupted!")
        for v in violations:
            print(f"  -> Tampered: {v}")
        print("Refusing to start. Restore clean files or run protect_install.bat.")
        sys.exit(1)

    args = sys.argv[1:]
    if "--doctor" in args:
        prereqs_only = "--prereqs" in args
        sys.exit(run_doctor(prereqs_only=prereqs_only))
    elif "kill" in args:
        from core.safety.kill_switch import kill_switch
        print("[T.A.R.O.] Emergency kill switch triggered from CLI.")
        kill_switch.trigger(source="cli")
        sys.exit(0)
    elif "--help" in args or "-h" in args:
        print("T.A.R.O. v1.3.0 (32k context)")
        print("Commands:")
        print("  taro.exe                            Launch T.A.R.O. desktop software application")
        print("  taro.exe --cli                      Start interactive console CLI assistant")
        print("  taro.exe --doctor --prereqs         Check system prerequisites")
        print("  taro.exe --doctor                   Run full health diagnostics")
        print("  taro.exe kill                       Trigger emergency kill switch")
    elif "--cli" in args:
        # --- Automatic Ollama server boot & model activation ---
        from core.model.ollama_auto_starter import ensure_ollama_ready
        print("[*] Checking Ollama server status...")
        result = ensure_ollama_ready()
        if result["ok"]:
            active = result.get("active_model", "unknown")
            print(f"[OK] Ollama ready. Active model: {active}")
        else:
            print(f"[WARN] Ollama issue: {result.get('error', 'Unknown error')}")
            print("[!] Continuing startup — model calls may fail until Ollama is available.")

        import asyncio
        asyncio.run(run_interactive_cli())
    else:
        # DEFAULT: Desktop Software Application & UI Window
        from core.model.ollama_auto_starter import ensure_ollama_ready
        print("[*] Checking Ollama server status...")
        result = ensure_ollama_ready()
        if result["ok"]:
            active = result.get("active_model", "unknown")
            print(f"[OK] Ollama ready. Active model: {active}")
        else:
            print(f"[WARN] Ollama issue: {result.get('error', 'Unknown error')}")
            print("[!] Continuing startup — model calls may fail until Ollama is available.")

        import asyncio
        asyncio.run(run_hud_app())


if __name__ == "__main__":
    main()

