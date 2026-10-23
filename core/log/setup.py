"""T.A.R.O. - Structured logging setup with secret masking.

ARCHITECTURE reference: sections 15, RULES section 4, 6.
TASKS: TASK-004.

Sets up structlog with JSON output to rotating log files and rich console
output for development. Masks secrets before any log record is emitted.

Usage:
    from core.log import get_logger
    log = get_logger(__name__)
    log.info("tool_called", tool="file.copy", status="ok")
"""

from __future__ import annotations

import logging
import logging.handlers
import re
import sys
from pathlib import Path
from typing import Any, cast

import structlog

# ---------------------------------------------------------------------------
# Secret masking
# ---------------------------------------------------------------------------

_SECRET_KEY_PATTERNS = re.compile(
    r"(key|token|secret|password|passwd|pwd|api_key|apikey|auth|credential)",
    re.IGNORECASE,
)

_SECRET_STRING_PATTERNS = re.compile(
    r"((?:api[_-]?key|token|secret|password|bearer|auth)[=:\s]+)(['\"]?[\w\-\.]{3,}['\"]?)",
    re.IGNORECASE,
)

_MASKED = "[REDACTED]"


def mask_secrets(value: Any) -> Any:
    """Recursively mask secret values in dicts, lists, and strings."""
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for k, v in value.items():
            k_str = str(k)
            if _SECRET_KEY_PATTERNS.search(k_str):
                result[k_str] = _MASKED
            else:
                result[k_str] = mask_secrets(v)
        return result
    if isinstance(value, list):
        return [mask_secrets(item) for item in value]
    if isinstance(value, str):
        # Mask inline patterns like API_KEY=abc
        return _SECRET_STRING_PATTERNS.sub(rf"\1{_MASKED}", value)
    return value


def _masking_processor(logger: Any, method: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    """Structlog processor that masks secret-looking key-value pairs."""
    return cast(dict[str, Any], mask_secrets(event_dict))


# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

_LOGS_ROOT = Path("logs")
_CONFIGURED = False


def setup_logging(
    level: str = "INFO",
    logs_root: Path | None = None,
    force: bool = False,
) -> None:
    """Configure structlog and stdlib logging.

    Call once at startup from main.py. Safe to call multiple times (idempotent).

    Args:
        level: Logging level string (DEBUG, INFO, WARNING, ERROR).
        logs_root: Override log directory (for tests).
        force: Force reconfiguration even if already configured.
    """
    global _CONFIGURED
    if _CONFIGURED and not force and logs_root is None:
        return
    _CONFIGURED = True

    root = logs_root or _LOGS_ROOT
    root.mkdir(parents=True, exist_ok=True)
    (root / "core").mkdir(parents=True, exist_ok=True)

    stdlib_level = getattr(logging, level.upper(), logging.INFO)

    # Rotating file handler
    file_handler = logging.handlers.RotatingFileHandler(
        root / "core" / "taro.log",
        maxBytes=10 * 1024 * 1024,
        backupCount=7,
        encoding="utf-8",
    )
    file_handler.setLevel(stdlib_level)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(stdlib_level)

    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        _masking_processor,
        structlog.stdlib.add_logger_name,
    ]

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.dev.ConsoleRenderer(colors=True),
        ],
    )
    console_handler.setFormatter(formatter)

    file_formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.processors.JSONRenderer(),
        ],
    )
    file_handler.setFormatter(file_formatter)

    logging.basicConfig(
        level=stdlib_level,
        handlers=[file_handler, console_handler],
        force=True,
    )

    structlog.configure(
        processors=shared_processors
        + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.make_filtering_bound_logger(stdlib_level),
        cache_logger_on_first_use=False,
    )


def get_logger(name: str) -> structlog.BoundLogger:
    """Return a bound structlog logger for the given module name."""
    if not _CONFIGURED:
        setup_logging()
    return cast(structlog.BoundLogger, structlog.get_logger(name))
