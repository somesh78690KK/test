"""T.A.R.O. - Microphone self-test (TASK-068).

ARCHITECTURE reference: section 9 (Voice Pipeline).
RULES reference: section 3, 10.
TASKS: TASK-068.

Runs a diagnostic self-test on the default audio input device.
Reports device name, measured input level (RMS), and pass/fail status.
"""

from __future__ import annotations

import time
from typing import Any

import numpy as np

from core.log.setup import get_logger

logger = get_logger(__name__)


def run_mic_self_test(duration_s: float = 0.5) -> dict[str, Any]:
    """Execute microphone self-test.

    Acceptance (TASK-068): Reports device name, level, and pass/fail.

    Args:
        duration_s: Duration in seconds to sample audio level.

    Returns:
        dict with keys:
            - device_name (str): Name of detected input device.
            - level (float): Measured RMS audio level.
            - passed (bool): True if device opened and samples captured.
            - details (str): Human-readable summary.
    """
    try:
        import sounddevice as sd
    except ImportError:
        logger.warning("mic_test_sounddevice_missing")
        return {
            "device_name": "unknown (sounddevice missing)",
            "level": 0.0,
            "passed": False,
            "details": "sounddevice library is not installed",
        }

    device_name = "None"
    try:
        device_info = sd.query_devices(kind="input")
        if isinstance(device_info, dict):
            device_name = str(device_info.get("name", "Unknown Input Device"))
        else:
            device_name = "Default Input Device"
    except Exception as e:
        logger.warning("mic_test_device_query_failed", error=str(e))
        return {
            "device_name": "No input device found",
            "level": 0.0,
            "passed": False,
            "details": f"Failed to query input device: {e}",
        }

    sample_rate = 16000
    num_samples = int(sample_rate * duration_s)

    try:
        recording = sd.rec(
            num_samples,
            samplerate=sample_rate,
            channels=1,
            dtype="int16",
            blocking=True,
        )
        rms = float(np.sqrt(np.mean(recording.astype(np.float32) ** 2)))
        passed = True
        details = f"Device '{device_name}' operational with RMS level {rms:.1f}."
        logger.info(
            "mic_self_test_passed",
            device=device_name,
            level=round(rms, 2),
        )
        return {
            "device_name": device_name,
            "level": round(rms, 2),
            "passed": passed,
            "details": details,
        }
    except Exception as e:
        logger.error("mic_self_test_record_failed", device=device_name, error=str(e))
        return {
            "device_name": device_name,
            "level": 0.0,
            "passed": False,
            "details": f"Recording failed on '{device_name}': {e}",
        }
