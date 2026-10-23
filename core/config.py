"""T.A.R.O. - Core configuration loader.

Loads config.yaml, merges config.local.yaml, validates with pydantic, and
exposes a singleton ``cfg`` object. Import from here everywhere.

ARCHITECTURE reference: section 13.
TASKS: TASK-003.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

# ---------------------------------------------------------------------------
# Section models
# ---------------------------------------------------------------------------


class StrictBase(BaseModel):
    """Base model forbidding unexpected extra fields to detect typos."""

    model_config = ConfigDict(extra="forbid")


class ModelConfig(StrictBase):
    chat_model: str = "richardyoung/qwen3-8b-abliterated:Q4_K_M"
    backup_model: str = "nemotron-3-nano:4b"
    vision_model: str = "moondream:latest"
    ollama_host: str = "http://127.0.0.1:11434"
    num_ctx: int = 32768
    num_predict: int = 2048
    num_gpu: int | Literal["auto"] = "auto"
    temperature: float = 0.3
    top_p: float = 0.9
    keep_alive: str = "10m"
    think: bool = False
    vision_unload_after_s: int = 30
    vram_low_watermark_gb: float = 1.0
    vram_ceiling_gb: float = 5.5


class OrchestratorConfig(StrictBase):
    max_steps: int = 12
    tool_timeout_s: int = 30
    summary_every_n_turns: int = 5
    summary_min_tokens: int = 250
    summary_max_tokens: int = 350


class PromptBudgetConfig(StrictBase):
    system: int = 1500
    tools: int = 4000
    profile_and_memory: int = 2000
    summary: int = 2000
    recent_turns: int = 20000
    response_reserve: int = 3268


class SafetyConfig(StrictBase):
    confirmation_timeout_s: int = 120
    kill_hotkey: str = "ctrl+alt+f12"
    audit_log_dir: str = "logs/audit"
    max_undo_days: int = 30
    sandbox_timeout_s: int = 30
    sandbox_dir: str = "sandbox"


class VoiceConfig(StrictBase):
    enabled: bool = True
    wake_word: str = "taro"
    wake_word_model: str = "models/taro_wakeword.onnx"
    push_to_talk_key: str = "space"
    hands_free: bool = True
    stt_engine: str = "vosk"
    stt_model_path: str = "models/vosk-model-small-en-us-0.15"
    stt_sample_rate: int = 16000
    max_utterance_s: int = 8
    silence_pause_s: float = 1.0
    tts_engine: str = "pyttsx3"
    tts_voice: str | None = None
    tts_rate: int = 150
    tts_emotional: bool = True


class VisionConfig(StrictBase):
    capture_width: int = 640
    capture_height: int = 360
    jpeg_quality: int = 75
    vlm_min_chars: int = 20
    capture_exclude_titles: list[str] = Field(
        default_factory=lambda: [
            "KeePass",
            "1Password",
            "Bitwarden",
            "Online Banking",
            "Credential Manager",
        ]
    )


class MemoryConfig(StrictBase):
    conversation_retention_days: int = 90
    recall_top_k: int = 4
    recall_min_similarity: float = 0.35
    embedding_model_path: str = "models/all-MiniLM-L6-v2"
    superseded_retention_days: int = 30
    recovery_retention_days: int = 30
    backup_keep_count: int = 7


class FilesConfig(StrictBase):
    workspace_root: str = "%USERPROFILE%\\TARO\\workspace"
    sandbox_root: str = "%USERPROFILE%\\TARO\\sandbox"
    recovery_root: str = "data/recovery"


class UIConfig(StrictBase):
    theme: str = "dark"
    min_width: int = 800
    min_height: int = 600
    recommended_width: int = 1200
    recommended_height: int = 800
    telemetry_refresh_s: int = 1


class ServicesConfig(StrictBase):
    app_monitor: bool = True
    scheduler: bool = True
    security_guardian: bool = False
    notification_guardian: bool = False
    screen_watcher: bool = False


class CloudConfig(StrictBase):
    gemini_enabled: bool = False
    openai_enabled: bool = False
    groq_enabled: bool = False
    anthropic_enabled: bool = False
    forge_cloud_draft: bool = False
    google_stt_enabled: bool = False


class SkillsConfig(StrictBase):
    skills_dir: str = "skills"
    generated_dir: str = "skills/_generated"
    forge_approval_mode: str = "ask"
    trial_confirmation_count: int = 3


class LoggingConfig(StrictBase):
    level: str = "INFO"
    rotate_mb: int = 10
    keep_days: int = 7


class AnalyticsConfig(StrictBase):
    enabled: bool = True


# ---------------------------------------------------------------------------
# Root config
# ---------------------------------------------------------------------------


class TaroConfig(StrictBase):
    """Root configuration object. Validated at startup."""

    model: ModelConfig = Field(default_factory=ModelConfig)
    orchestrator: OrchestratorConfig = Field(default_factory=OrchestratorConfig)
    prompt_budget: PromptBudgetConfig = Field(default_factory=PromptBudgetConfig)
    safety: SafetyConfig = Field(default_factory=SafetyConfig)
    voice: VoiceConfig = Field(default_factory=VoiceConfig)
    vision: VisionConfig = Field(default_factory=VisionConfig)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    files: FilesConfig = Field(default_factory=FilesConfig)
    ui: UIConfig = Field(default_factory=UIConfig)
    services: ServicesConfig = Field(default_factory=ServicesConfig)
    cloud: CloudConfig = Field(default_factory=CloudConfig)
    skills: SkillsConfig = Field(default_factory=SkillsConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    analytics: AnalyticsConfig = Field(default_factory=AnalyticsConfig)


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

_CONFIG_DIR = Path(__file__).parent.parent / "config"


def _load_yaml(path: Path) -> dict[str, Any]:
    """Load a YAML file; return empty dict if it does not exist."""
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge override into base (override wins)."""
    result = dict(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config(config_path_or_dir: Path | str | None = None) -> TaroConfig:
    """Load, merge, and validate the configuration.

    Args:
        config_path_or_dir: Override config directory or single yaml file.

    Returns:
        A validated TaroConfig instance.

    Raises:
        SystemExit: On validation failure.
    """
    if config_path_or_dir is None:
        cdir = _CONFIG_DIR
        base = _load_yaml(cdir / "config.yaml")
        local = _load_yaml(cdir / "config.local.yaml")
    else:
        p = Path(config_path_or_dir)
        if p.is_file():
            base = _load_yaml(p)
            local = {}
        else:
            base = _load_yaml(p / "config.yaml")
            local = _load_yaml(p / "config.local.yaml")

    merged = _deep_merge(base, local)

    try:
        return TaroConfig.model_validate(merged)
    except ValidationError as exc:
        fields = ", ".join(str(e["loc"]) for e in exc.errors())
        msg = f"[T.A.R.O.] Configuration error in field(s): {fields}"
        print(msg)
        for error in exc.errors():
            print(f"  {error['loc']}: {error['msg']}")
        raise SystemExit(1) from exc


# Singleton - import `cfg` everywhere
cfg: TaroConfig = load_config()


def get_config() -> TaroConfig:
    """Return the global configuration instance."""
    return cfg
