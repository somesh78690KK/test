"""T.A.R.O. - Wake word detector (TASK-065).

ARCHITECTURE reference: section 9 (Voice Pipeline).
RULES reference: section 3, 10.
TASKS: TASK-065.

Wake word detection using a simple energy + keyword approach.
Does NOT poll Whisper - uses a lightweight detector to avoid CPU waste.
Push-to-talk (hold a key) always works as fallback.
"""

from __future__ import annotations

import asyncio
import threading
import time
from pathlib import Path
from typing import Callable

import numpy as np

from core.log.setup import get_logger

logger = get_logger(__name__)


def _get_resource_path(relative_path: str) -> Path:
    """Get the correct path for a resource file, handling frozen executable mode."""
    import sys
    if getattr(sys, 'frozen', False):
        # Running in PyInstaller bundle
        base_path = Path(sys._MEIPASS)
    else:
        # Running in development mode
        base_path = Path(__file__).resolve().parents[1]
    return base_path / relative_path


def _load_voice_config() -> dict:
    """Load voice config from config.yaml."""
    try:
        import yaml

        cfg_path = Path(__file__).resolve().parents[1] / "config" / "config.yaml"
        if cfg_path.exists():
            with open(cfg_path, "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f) or {}
            return cfg.get("voice", {})
    except Exception:
        pass
    return {}


_VOICE_CFG = _load_voice_config()
WAKE_WORD = _VOICE_CFG.get("wake_word", "taro")
WAKE_WORD_MODEL_PATH = _get_resource_path(_VOICE_CFG.get("wake_word_model", "models/taro_wakeword.onnx"))
PUSH_TO_TALK_KEY = _VOICE_CFG.get("push_to_talk_key", "space")
HANDS_FREE = _VOICE_CFG.get("hands_free", True)

SAMPLE_RATE = 16000
CHUNK_DURATION_S = 0.5  # 500 ms chunks for wake word
CHUNK_SAMPLES = int(SAMPLE_RATE * CHUNK_DURATION_S)
ENERGY_THRESHOLD = 800  # Increased to reduce background noise sensitivity


class WakeWordDetector:
    """Lightweight wake word detector.

    Strategy:
    1. Listen for energy above threshold (someone is speaking).
    2. When energy detected, capture a short buffer (~2s).
    3. Run faster-whisper on that buffer to check for the wake word.

    This avoids constantly running Whisper (which would burn CPU).
    The detector only triggers Whisper when there's actual speech energy,
    keeping idle CPU under 4%.

    Push-to-talk is always available as a fallback.
    """

    def __init__(self, on_wake: Callable[[], None] | None = None, hands_free: bool | None = None):
        self.wake_word = WAKE_WORD.lower()
        self.on_wake = on_wake
        self._running = False
        self._thread: threading.Thread | None = None
        self._stt_engine = None
        self._push_to_talk_active = False
        self._cooldown_s = 2.0  # Min time between detections
        self._hands_free = hands_free if hands_free is not None else HANDS_FREE

    def start(self) -> None:
        """Start wake word detection in background thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._thread.start()
        logger.info("wake_word_started", wake_word=self.wake_word)

    def stop(self) -> None:
        """Stop wake word detection."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=3.0)
            self._thread = None
        logger.info("wake_word_stopped")

    def _get_stt(self) -> "STTEngine":
        """Lazy-load a shared STT engine for wake word checks."""
        if self._stt_engine is None:
            from voice.stt import STTEngine

            self._stt_engine = STTEngine()
        return self._stt_engine

    def _listen_loop(self) -> None:
        """Main listening loop (runs in background thread)."""
        try:
            import sounddevice as sd
        except ImportError:
            logger.error("sounddevice_not_available")
            return

        last_detection = 0.0

        while self._running:
            try:
                # Record a chunk
                chunk = sd.rec(
                    CHUNK_SAMPLES,
                    samplerate=SAMPLE_RATE,
                    channels=1,
                    dtype="int16",
                    blocking=True,
                )

                if not self._running:
                    break

                # Check energy - require sustained speech energy
                rms = np.sqrt(np.mean(chunk.astype(np.float32) ** 2))
                if rms < ENERGY_THRESHOLD:
                    continue  # Silence, skip

                # Additional check: verify this isn't just a brief spike
                # by requiring multiple consecutive high-energy chunks
                self._energy_buffer = getattr(self, '_energy_buffer', [])
                self._energy_buffer.append(rms)
                if len(self._energy_buffer) > 3:
                    self._energy_buffer.pop(0)

                # Need at least 2 consecutive high-energy chunks
                if len(self._energy_buffer) < 2 or sum(self._energy_buffer[-2:]) < ENERGY_THRESHOLD * 1.5:
                    continue

                # Cooldown check
                now = time.monotonic()
                if now - last_detection < self._cooldown_s:
                    continue

                # In hands-free mode, trigger recording directly on speech detection
                if self._hands_free:
                    logger.debug("hands_free_speech_detected", rms=round(rms, 1))
                    last_detection = time.monotonic()
                    if self.on_wake:
                        self.on_wake()
                    # Add longer cooldown to prevent rapid triggering
                    time.sleep(0.5)
                    continue

                # Energy detected! Record a longer buffer for wake word check
                logger.debug("wake_word_energy_detected", rms=round(rms, 1))

                # Capture ~2 seconds more
                extra_chunks = int(2.0 / CHUNK_DURATION_S)
                audio_parts = [chunk.flatten()]
                for _ in range(extra_chunks):
                    if not self._running:
                        break
                    extra = sd.rec(
                        CHUNK_SAMPLES,
                        samplerate=SAMPLE_RATE,
                        channels=1,
                        dtype="int16",
                        blocking=True,
                    )
                    audio_parts.append(extra.flatten())

                # Transcribe the buffer
                audio = np.concatenate(audio_parts)
                stt = self._get_stt()
                text = stt.transcribe_audio(audio, SAMPLE_RATE).lower()

                # Check for wake word (with flexible matching)
                wake_detected = self.wake_word in text or any(
                    self.wake_word in word for word in text.split()
                )

                if wake_detected:
                    last_detection = time.monotonic()
                    logger.info("wake_word_detected", text=text[:50])
                    if self.on_wake:
                        self.on_wake()

            except Exception as e:
                if self._running:
                    logger.error("wake_word_loop_error", error=str(e))
                    time.sleep(1.0)  # Prevent tight error loop

    def trigger_push_to_talk(self) -> None:
        """Signal that push-to-talk was activated."""
        logger.info("push_to_talk_triggered")
        if self.on_wake:
            self.on_wake()
