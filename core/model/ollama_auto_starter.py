"""T.A.R.O. - Automatic Ollama Server Lifecycle & Model Activator.

Guarantees seamless desktop assistant startup:
1. Probes local Ollama server status (http://127.0.0.1:11434).
2. If inactive or stopped, automatically locates the Ollama binary and launches `ollama serve` in the background.
3. Polls until the server is alive and responding.
4. Pre-warms and activates the configured model into GPU memory for zero-lag first response.
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from core.config import cfg
from core.log.setup import get_logger

logger = get_logger(__name__)

COMMON_OLLAMA_PATHS = [
    Path(os.path.expandvars(r"%LOCALAPPDATA%\Programs\Ollama\ollama.exe")),
    Path(os.path.expandvars(r"%LOCALAPPDATA%\Programs\Ollama\ollama app.exe")),
    Path(r"C:\Users\Somesh\AppData\Local\Programs\Ollama\ollama.exe"),
    Path(r"C:\Program Files\Ollama\ollama.exe"),
    Path(r"C:\Program Files (x86)\Ollama\ollama.exe"),
]


def find_ollama_executable() -> Path | None:
    """Finds the Ollama executable on PATH or standard Windows install directories."""
    # 1. Check PATH
    bin_on_path = shutil.which("ollama")
    if bin_on_path:
        return Path(bin_on_path)

    # 2. Check standard Windows locations
    for p in COMMON_OLLAMA_PATHS:
        if p.exists():
            return p

    return None


def is_ollama_server_active(host: str = "http://127.0.0.1:11434", timeout_s: float = 1.5) -> bool:
    """Pings the Ollama HTTP API to verify if the server is alive and ready."""
    url = f"{host.rstrip('/')}/api/tags"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "TARO-AutoStarter/1.0"})
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            return resp.status == 200
    except Exception:
        return False


def get_installed_ollama_models(host: str = "http://127.0.0.1:11434") -> list[str]:
    """Retrieves names of all locally pulled/installed models."""
    url = f"{host.rstrip('/')}/api/tags"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "TARO-AutoStarter/1.0"})
        with urllib.request.urlopen(req, timeout=3.0) as resp:
            data = json.loads(resp.read().decode())
            return [m.get("name", "") for m in data.get("models", [])]
    except Exception as e:
        logger.debug("get_installed_models_error", error=str(e))
        return []


def start_ollama_server(ollama_bin: Path | None = None) -> subprocess.Popen | None:
    """Spawns Ollama server process in the background without opening a blocking terminal window."""
    bin_path = ollama_bin or find_ollama_executable()
    if not bin_path or not bin_path.exists():
        logger.error("ollama_binary_not_found_for_autostart")
        return None

    # Ensure 6GB VRAM safety environment variable
    env = dict(os.environ)
    if "OLLAMA_MAX_LOADED_MODELS" not in env:
        env["OLLAMA_MAX_LOADED_MODELS"] = "1"

    logger.info("launching_ollama_server", binary=str(bin_path))
    print(f"[+] Ollama server is not running. Automatically starting {bin_path.name} in background...")

    creation_flags = 0
    if os.name == "nt":
        # Windows flag to launch process in background without popping up a console window
        creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)

    try:
        proc = subprocess.Popen(
            [str(bin_path), "serve"],
            env=env,
            creationflags=creation_flags,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return proc
    except Exception as e:
        logger.error("failed_to_spawn_ollama_server", error=str(e))
        return None


def activate_model(
    model_name: str,
    host: str = "http://127.0.0.1:11434",
    timeout_s: float = 30.0,
) -> bool:
    """Sends a lightweight pre-warm request to load and activate the model in GPU memory."""
    url = f"{host.rstrip('/')}/api/generate"
    payload = {
        "model": model_name,
        "prompt": "",
        "keep_alive": "10m",
    }
    try:
        logger.info("prewarming_model", model=model_name)
        data_bytes = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data_bytes,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            return resp.status == 200
    except Exception as e:
        logger.warning("model_prewarm_notice", model=model_name, error=str(e))
        return False


def ensure_ollama_ready(
    host: str | None = None,
    target_model: str | None = None,
    max_wait_s: float = 20.0,
) -> dict[str, Any]:
    """Ensures Ollama is active, starts it if down, and activates the required model.

    Returns diagnostic status dict with details on server state and active model.
    """
    server_host = host or cfg.model.ollama_host
    preferred_model = target_model or cfg.model.chat_model

    # 1. Check if already alive
    if not is_ollama_server_active(server_host):
        ollama_bin = find_ollama_executable()
        if not ollama_bin:
            return {
                "ok": False,
                "server_running": False,
                "error": "Ollama executable not found on host. Please install Ollama from https://ollama.com",
            }

        start_ollama_server(ollama_bin)

        # Wait for server to come up
        start_time = time.monotonic()
        started = False
        while (time.monotonic() - start_time) < max_wait_s:
            time.sleep(0.5)
            if is_ollama_server_active(server_host):
                started = True
                break

        if not started:
            return {
                "ok": False,
                "server_running": False,
                "error": f"Ollama server was launched but failed to respond at {server_host} within {max_wait_s}s.",
            }
        print(f"[OK] Ollama server is now online at {server_host}!")

    # 2. Inspect available models
    installed = get_installed_ollama_models(server_host)
    if not installed:
        return {
            "ok": True,
            "server_running": True,
            "active_model": None,
            "warning": "Ollama server is active, but no models are currently installed.",
        }

    # Match preferred model or fallback
    chosen_model = None
    for m in installed:
        if preferred_model in m or m in preferred_model:
            chosen_model = m
            break

    # If preferred model tag not exact match, try 'taro:latest', 'qwen3', or backup
    if not chosen_model:
        for fallback_name in ["taro:latest", "nemotron-3-nano:4b", cfg.model.backup_model]:
            for m in installed:
                if fallback_name in m:
                    chosen_model = m
                    break
            if chosen_model:
                break

    if not chosen_model and installed:
        chosen_model = installed[0]

    # 3. Activate/pre-warm model
    if chosen_model:
        activate_model(chosen_model, host=server_host, timeout_s=30.0)

    return {
        "ok": True,
        "server_running": True,
        "active_model": chosen_model,
        "installed_models": installed,
        "server_host": server_host,
    }
