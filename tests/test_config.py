"""T.A.R.O. - Configuration tests.

TASKS: TASK-003.
Acceptance test: Invalid field stops startup and names the field.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from core.config import TaroConfig, cfg, load_config


def test_cfg_singleton_loaded() -> None:
    """Verifies that the default configuration loads with correct model settings."""
    assert cfg.model.chat_model == "richardyoung/qwen3-8b-abliterated:Q4_K_M"
    assert cfg.model.backup_model == "nemotron-3-nano:4b"
    assert cfg.model.num_ctx == 32768


def test_invalid_field_stops_startup_and_names_field(capsys: pytest.CaptureFixture[str]) -> None:
    """TASK-003 acceptance test: an invalid field raises SystemExit and prints the field name."""
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".yaml", encoding="utf-8") as f:
        f.write("unknown_bogus_field_xyz: 999\n")
        f_path = Path(f.name)

    try:
        with pytest.raises(SystemExit) as exc_info:
            load_config(f_path)
        assert exc_info.value.code == 1

        captured = capsys.readouterr()
        assert "unknown_bogus_field_xyz" in captured.out
    finally:
        if f_path.exists():
            f_path.unlink()
