"""T.A.R.O. - Vosk-based Speech-to-Text Engine.

Lightweight, offline-capable STT using Vosk Kaldi models.
Replaces faster-whisper for lower resource usage and instant startup.
"""

from __future__ import annotations

import json
import queue
import threading
from pathlib import Path
from typing import Any

import sounddevice as sd
import vosk
from core.log.setup import get_logger

logger = get_logger(__name__)

SAMPLE_RATE = 16000
CHANNELS = 1
DTYPE = "int16"

# Model path
MODEL_PATH = Path("models/vosk-model-small-en-us-0.15")


class VoskSTTEngine:
    """Vosk-based speech recognition engine."""

    def __init__(self, model_path: Path | str | None = None):
        self.model_path = Path(model_path) if model_path else MODEL_PATH
        self.model = None
        self.recognizer = None
        self._loaded = False

    def load_model(self) -> bool:
        """Load the Vosk model."""
        try:
            if not self.model_path.exists():
                logger.error("vosk_model_not_found", path=str(self.model_path))
                return False

            logger.info("stt_loading_model", engine="vosk", path=str(self.model_path))
            self.model = vosk.Model(str(self.model_path))
            self.recognizer = vosk.KaldiRecognizer(self.model, SAMPLE_RATE)
            self._loaded = True
            logger.info("stt_model_loaded", engine="vosk")
            return True
        except Exception as e:
            logger.error("stt_load_error", error=str(e))
            return False

    def transcribe_audio(self, audio_data: bytes) -> str:
        """Transcribe audio data to text."""
        if not self._loaded:
            if not self.load_model():
                return ""

        try:
            self.recognizer.AcceptWaveform(audio_data)
            result = json.loads(self.recognizer.Result())
            text = result.get("text", "").strip()
            logger.info("stt_transcription", text=text)
            return text
        except Exception as e:
            logger.error("stt_transcription_error", error=str(e))
            return ""

    def transcribe_stream(self, duration: float = 2.0) -> str:
        """Record and transcribe audio from microphone."""
        if not self._loaded:
            if not self.load_model():
                return ""

        try:
            # Record audio
            audio_queue = queue.Queue()

            def callback(indata, frames, time, status):
                if status:
                    logger.warning("audio_callback_status", status=str(status))
                audio_queue.put(bytes(indata))

            with sd.RawInputStream(
                samplerate=SAMPLE_RATE,
                channels=CHANNELS,
                dtype=DTYPE,
                callback=callback,
            ):
                logger.info("stt_recording", duration=duration)
                sd.sleep(int(duration * 1000))

            # Process audio
            all_audio = b""
            while not audio_queue.empty():
                all_audio += audio_queue.get()

            return self.transcribe_audio(all_audio)
        except Exception as e:
            logger.error("stt_stream_error", error=str(e))
            return ""

    def finalize(self) -> str:
        """Get final partial result."""
        if not self._loaded:
            return ""
        try:
            result = json.loads(self.recognizer.FinalResult())
            return result.get("text", "").strip()
        except Exception:
            return ""


# Global instance
_vosk_engine: VoskSTTEngine | None = None


def get_vosk_engine() -> VoskSTTEngine:
    """Get or create the global Vosk STT engine."""
    global _vosk_engine
    if _vosk_engine is None:
        _vosk_engine = VoskSTTEngine()
    return _vosk_engine


def transcribe(duration: float = 2.0) -> str:
    """Convenience function to transcribe from microphone."""
    engine = get_vosk_engine()
    return engine.transcribe_stream(duration)
