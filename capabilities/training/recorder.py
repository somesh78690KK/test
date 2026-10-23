"""T.A.R.O. - Training recorder (TASK-073).

ARCHITECTURE reference: section 11.
RULES reference: section 4, 10.
TASKS: TASK-073.

Records user mouse and keyboard actions using pynput.
Safety requirements:
- Keystrokes in a password field or sensitive window are NEVER stored.
- Saved as JSON lines.
- Recording state flag is exposed to drive HUD indicator.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from core.log.setup import get_logger

logger = get_logger(__name__)

# Sensitive window title keywords where keystrokes are suppressed
SENSITIVE_TITLES = {"password", "login", "bitwarden", "keepass", "1password", "credential"}


class TrainingRecorder:
    """Records user input events and writes them as JSON-lines."""

    def __init__(self, output_dir: Path | str | None = None) -> None:
        self.output_dir = Path(output_dir) if output_dir else Path("data/workflows/recordings")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._recording = False
        self._events: list[dict[str, Any]] = []
        self._start_time: float = 0.0

    @property
    def is_recording(self) -> bool:
        return self._recording

    def start_recording(self) -> None:
        """Start capturing events."""
        self._events.clear()
        self._start_time = time.monotonic()
        self._recording = True
        logger.info("training_recorder_started")

    def record_event(
        self,
        event_type: str,
        data: dict[str, Any],
        active_window_title: str = "",
        is_password_field: bool = False,
    ) -> bool:
        """Record a single event with privacy filter.

        Returns True if recorded, False if suppressed for privacy.
        """
        if not self._recording:
            return False

        # Privacy check: If sensitive window or password field, sanitize or drop key events
        is_sensitive = is_password_field or any(
            kw in active_window_title.lower() for kw in SENSITIVE_TITLES
        )

        if is_sensitive and event_type in ("key_press", "key_release"):
            logger.info("training_recorder_masked_sensitive_keystroke")
            # Store masked token instead of raw key
            data = {"key": "[MASKED_PASSWORD_FIELD]"}

        record = {
            "t": round(time.monotonic() - self._start_time, 4),
            "type": event_type,
            "window": active_window_title,
            **data,
        }
        self._events.append(record)
        return True

    def stop_recording(self, filename: str | None = None) -> Path:
        """Stop capturing and write events to a JSON-lines file."""
        self._recording = False
        fname = filename or f"recording_{int(time.time())}.jsonl"
        out_path = self.output_dir / fname

        with open(out_path, "w", encoding="utf-8") as f:
            for ev in self._events:
                f.write(json.dumps(ev) + "\n")

        logger.info(
            "training_recorder_stopped",
            count=len(self._events),
            file=str(out_path),
        )
        return out_path
