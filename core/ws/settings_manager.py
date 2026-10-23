"""T.A.R.O. - HUD Settings Manager (TASK-085).

ARCHITECTURE reference: section 24.
TASKS: TASK-085.

Backend service for the Settings modal - provides read/write access to
configuration sections via WebSocket messages:
  - General, Voice, Vision, Models, Permissions, Skills, Workflows, Logs.

Each tab saves and reloads config through core/config.py.

Acceptance (TASK-085): Each tab saves and reloads config.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.log.setup import get_logger

logger = get_logger(__name__)

# Settings sections matching the HUD tabs
SETTINGS_SECTIONS = [
    "general",
    "voice",
    "vision",
    "models",
    "permissions",
    "skills",
    "workflows",
    "logs",
]


class SettingsManager:
    """Manages settings read/write for the HUD settings modal."""

    def __init__(self, config: Any = None) -> None:
        self._config = config
        self._overrides: dict[str, dict[str, Any]] = {}
        self._load_overrides()

    def _overrides_path(self) -> Path:
        return Path("config/config.local.yaml")

    def _load_overrides(self) -> None:
        """Load local overrides if they exist."""
        p = self._overrides_path()
        if p.exists():
            try:
                import yaml
                with open(p, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
                self._overrides = data
            except Exception:
                self._overrides = {}

    def get_all_settings(self) -> dict[str, Any]:
        """Return all settings grouped by section for HUD display."""
        settings: dict[str, Any] = {}

        # General section
        settings["general"] = {
            "assistant_name": "T.A.R.O.",
            "language": "en",
            "theme": "dark",
            "start_minimized": False,
            "enable_notifications": True,
            "workspace_path": str(Path("workspace").resolve()),
        }

        # Voice section
        settings["voice"] = {
            "wake_word_enabled": True,
            "wake_word": "taro",
            "push_to_talk": True,
            "push_to_talk_key": "ctrl+space",
            "tts_engine": "edge-tts",
            "tts_voice": "en-US-GuyNeural",
            "stt_engine": "faster-whisper",
            "google_stt_consent": False,
        }

        # Vision section
        settings["vision"] = {
            "screen_capture_enabled": True,
            "ocr_enabled": True,
            "vlm_model": "moondream:latest",
            "vlm_auto_unload_s": 30,
            "camera_enabled": False,
            "sensitive_windows": ["KeePass", "1Password", "Bitwarden"],
        }

        # Models section
        settings["models"] = {
            "primary_model": "richardyoung/qwen3-8b-abliterated:Q4_K_M",
            "secondary_model": "nemotron3",
            "token_budget": 32768,
            "num_ctx": 32768,
            "cloud_enabled": False,
            "cloud_provider": "",
        }

        # Permissions section
        settings["permissions"] = {
            "files": "allow",
            "system": "ask",
            "browser": "allow",
            "office": "allow",
            "web": "allow",
            "coding": "ask",
        }

        # Skills section
        settings["skills"] = {
            "auto_discover": True,
            "skills_directory": str(Path("skills").resolve()),
            "forge_enabled": True,
            "forge_approval_mode": "ask",
        }

        # Workflows section
        settings["workflows"] = {
            "recording_enabled": True,
            "password_masking": True,
            "max_workflows": 50,
        }

        # Logs section
        settings["logs"] = {
            "log_level": "INFO",
            "log_format": "json",
            "secret_masking": True,
            "audit_enabled": True,
            "log_directory": str(Path("logs").resolve()),
        }

        # Apply overrides
        for section, overrides in self._overrides.items():
            if section in settings and isinstance(overrides, dict):
                settings[section].update(overrides)

        return settings

    def get_section(self, section: str) -> dict[str, Any]:
        """Get settings for a specific section."""
        all_settings = self.get_all_settings()
        return all_settings.get(section, {})

    def update_setting(self, section: str, key: str, value: Any) -> bool:
        """Update a single setting value."""
        if section not in SETTINGS_SECTIONS:
            logger.warning("invalid_settings_section", section=section)
            return False

        # Store in overrides
        if section not in self._overrides:
            self._overrides[section] = {}
        self._overrides[section][key] = value

        # Persist
        self._save_overrides()
        logger.info("setting_updated", section=section, key=key)
        return True

    def get_setting(self, section: str, key: str, default: Any = None) -> Any:
        """Get a single setting value."""
        sec = self.get_section(section)
        return sec.get(key, default)

    def set_setting(self, section: str, key: str, value: Any) -> bool:
        """Alias for update_setting."""
        return self.update_setting(section, key, value)

    def _save_overrides(self) -> None:
        """Persist overrides to config.local.yaml."""
        try:
            import yaml
            p = self._overrides_path()
            p.parent.mkdir(parents=True, exist_ok=True)
            with open(p, "w", encoding="utf-8") as f:
                yaml.safe_dump(self._overrides, f, default_flow_style=False)
        except ImportError:
            # YAML not available — write as JSON fallback
            p = Path("config/config.local.json")
            p.parent.mkdir(parents=True, exist_ok=True)
            with open(p, "w", encoding="utf-8") as f:
                json.dump(self._overrides, f, indent=2)

    def reset_section(self, section: str) -> bool:
        """Reset a section to defaults by removing overrides."""
        if section in self._overrides:
            del self._overrides[section]
            self._save_overrides()
            logger.info("settings_section_reset", section=section)
            return True
        return False
