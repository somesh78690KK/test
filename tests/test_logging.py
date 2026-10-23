"""T.A.R.O. - Logging and secret masking tests.

TASKS: TASK-004.
Acceptance test: Test log line containing API_KEY=abc is masked.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from core.log.setup import get_logger, mask_secrets, setup_logging


def test_mask_secrets_dict() -> None:
    """Verifies dictionary keys matching secrets are masked."""
    data = {
        "api_key": "secret_12345",
        "user_token": "token_abcde",
        "password": "my_password",
        "username": "public_user",
    }
    masked = mask_secrets(data)
    assert masked["api_key"] == "[REDACTED]"
    assert masked["user_token"] == "[REDACTED]"
    assert masked["password"] == "[REDACTED]"
    assert masked["username"] == "public_user"


def test_mask_secrets_inline_string() -> None:
    """TASK-004 acceptance: Test log line containing API_KEY=abc is masked."""
    line = "Authorization failed for API_KEY=abc_123456789 in request"
    masked = mask_secrets(line)
    assert "abc_123456789" not in masked
    assert "API_KEY=[REDACTED]" in masked


def test_logger_writes_to_file_and_masks() -> None:
    """Verifies that actual logger output written to disk has secrets redacted."""
    import logging

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        setup_logging(level="DEBUG", logs_root=tmp_path, force=True)
        log = get_logger("test_module")

        log.info("user_login", api_key="super_secret_token", note="test API_KEY=xyz_secret")

        log_file = tmp_path / "core" / "taro.log"
        assert log_file.exists()

        content = log_file.read_text(encoding="utf-8")
        assert "super_secret_token" not in content
        assert "xyz_secret" not in content
        assert "[REDACTED]" in content

        # Close handlers so Windows allows deleting tmp_dir
        for h in logging.root.handlers[:]:
            h.close()
            logging.root.removeHandler(h)
