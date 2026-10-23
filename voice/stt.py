"""T.A.R.O. - Speech-to-Text engine (TASK-065).

ARCHITECTURE reference: section 9 (Voice Pipeline).
RULES reference: section 3, 10.
TASKS: TASK-065.

STT pipeline:
  mic (sounddevice) -> VAD (energy-based) -> capture utterance
  -> Vosk (CPU, offline) -> text

Push-to-talk always available as fallback.
Runs on CPU, never touches VRAM.
"""

from __future__ import annotations

import asyncio
import io
import sys
import time
import wave
import threading
import struct
from pathlib import Path
from typing import Any, Callable

import numpy as np

from core.log.setup import get_logger

logger = get_logger(__name__)


def _get_resource_path(relative_path: str) -> Path:
    """Get the correct path for a resource file, handling frozen executable mode."""
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
STT_ENGINE = _VOICE_CFG.get("stt_engine", "vosk")
STT_MODEL_PATH = _get_resource_path(_VOICE_CFG.get("stt_model_path", "models/vosk-model-small-en-us-0.15"))
STT_SAMPLE_RATE = _VOICE_CFG.get("stt_sample_rate", 16000)
MAX_UTTERANCE_S = _VOICE_CFG.get("max_utterance_s", 8)
SILENCE_PAUSE_S = _VOICE_CFG.get("silence_pause_s", 1.0)
SAMPLE_RATE = STT_SAMPLE_RATE
CHANNELS = 1
CHUNK_DURATION_S = 0.03  # 30 ms chunks
CHUNK_SAMPLES = int(SAMPLE_RATE * CHUNK_DURATION_S)
# Energy-based VAD threshold (RMS) - increased to reduce sensitivity
ENERGY_THRESHOLD = 1200
# Minimum speech duration to consider valid (seconds)
MIN_SPEECH_DURATION_S = 0.5


class STTEngine:
    """Speech-to-Text engine using Vosk (offline, lightweight).

    Acceptance (TASK-065):
    - Push-to-talk works when wake word is off
    - Idle CPU under 4%
    - Instant startup (< 0.2s)
    """

    def __init__(
        self,
        model_path: str = STT_MODEL_PATH,
        sample_rate: int = STT_SAMPLE_RATE,
    ):
        self.model_path = model_path
        self.sample_rate = sample_rate
        self._model = None
        self._recognizer = None
        self._model_lock = threading.Lock()
        self._on_transcription: Callable[[str], None] | None = None
        self._recording = False
        self._listening = False
        self._recognizer_ready = False

    def on_transcription(self, callback: Callable[[str], None]) -> None:
        """Register a callback for completed transcriptions."""
        self._on_transcription = callback

    def _ensure_recognizer(self) -> Any:
        """Lazy-load the Vosk recognizer."""
        if self._recognizer_ready and self._recognizer is not None:
            return self._recognizer

        with self._model_lock:
            if self._recognizer_ready and self._recognizer is not None:
                return self._recognizer

            try:
                import vosk
                from pathlib import Path

                model_path = Path(self.model_path)
                if not model_path.exists():
                    # Try alternative path resolution for frozen mode
                    if getattr(sys, 'frozen', False):
                        # In frozen mode, models should be in _internal/models
                        alt_path = Path(sys._MEIPASS) / "models" / "vosk-model-small-en-us-0.15"
                        if alt_path.exists():
                            model_path = alt_path
                            logger.info("stt_using_alt_path", path=str(model_path))
                        else:
                            raise RuntimeError(f"Vosk model not found at {self.model_path} or {alt_path}")
                    else:
                        raise RuntimeError(f"Vosk model not found at {self.model_path}")

                logger.info("stt_loading_model", engine="vosk", path=str(model_path))
                self._model = vosk.Model(str(model_path))
                self._recognizer = vosk.KaldiRecognizer(self._model, self.sample_rate)
                self._recognizer_ready = True
                logger.info("stt_model_loaded", engine="vosk")
                return self._recognizer
            except ImportError:
                raise RuntimeError(
                    "vosk is required for STT. "
                    "Install with: pip install vosk"
                )

    def transcribe_audio(
        self,
        audio_data: np.ndarray,
        sample_rate: int = SAMPLE_RATE,
    ) -> str:
        """Transcribe audio numpy array to text using Vosk.

        Args:
            audio_data: numpy int16 array of audio samples.
            sample_rate: audio sample rate.

        Returns:
            Transcribed text string.
        """
        try:
            recognizer = self._ensure_recognizer()

            # Convert audio to bytes for Vosk
            audio_bytes = audio_data.astype(np.int16).tobytes()

            # Feed audio to recognizer
            if recognizer.AcceptWaveform(audio_bytes):
                import json
                result = json.loads(recognizer.Result())
                text = result.get("text", "").strip()
                logger.info("stt_transcription", text=text)
                return text

            # Get partial result if final not ready (silence logging to reduce spam)
            import json
            result = json.loads(recognizer.PartialResult())
            text = result.get("partial", "").strip()
            # Only log partials if they're substantial (reduce log spam)
            if text and len(text) > 3:
                logger.debug("stt_partial_transcription", text=text)
            return text

        except Exception as e:
            logger.error("stt_transcription_error", error=str(e))
            raise

    def transcribe_wav_bytes(self, wav_bytes: bytes) -> str:
        """Transcribe WAV file bytes to text."""
        buf = io.BytesIO(wav_bytes)
        with wave.open(buf, "rb") as wf:
            n_frames = wf.getnframes()
            raw = wf.readframes(n_frames)
            audio = np.frombuffer(raw, dtype=np.int16)
        return self.transcribe_audio(audio, SAMPLE_RATE)

    def transcribe_file(self, filepath: str) -> str:
        """Transcribe an audio file to text using Vosk."""
        recognizer = self._ensure_recognizer()
        
        with wave.open(filepath, "rb") as wf:
            sample_rate = wf.getframerate()
            if sample_rate != self.sample_rate:
                logger.warning("stt_sample_rate_mismatch", file_rate=sample_rate, expected=self.sample_rate)
            
            # Read and process audio in chunks
            text_parts = []
            while True:
                data = wf.readframes(4000)
                if len(data) == 0:
                    break
                if recognizer.AcceptWaveform(data):
                    import json
                    result = json.loads(recognizer.Result())
                    text = result.get("text", "").strip()
                    if text:
                        text_parts.append(text)
            
            # Get final result
            import json
            result = json.loads(recognizer.FinalResult())
            text = result.get("text", "").strip()
            if text:
                text_parts.append(text)
            
            return " ".join(text_parts).strip()

    async def record_and_transcribe(
        self,
        max_duration_s: float = MAX_UTTERANCE_S,
        silence_s: float = SILENCE_PAUSE_S,
    ) -> str:
        """Record from microphone until silence, then transcribe.

        Uses energy-based VAD to detect speech end.
        Returns transcribed text.
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, self._record_and_transcribe_sync, max_duration_s, silence_s
        )

    def _record_and_transcribe_sync(
        self, max_duration_s: float, silence_s: float
    ) -> str:
        """Synchronous record-and-transcribe (runs in thread pool)."""
        import sounddevice as sd

        self._recording = True
        logger.info("stt_recording_started")

        chunks: list[np.ndarray] = []
        silence_chunks = 0
        max_silence_chunks = int(silence_s / CHUNK_DURATION_S)
        max_chunks = int(max_duration_s / CHUNK_DURATION_S)
        speech_started = False
        energy_buffer = []  # For consecutive energy checks
        min_consecutive_energy = 2  # Require 2 consecutive high-energy chunks

        try:
            stream = sd.InputStream(
                samplerate=SAMPLE_RATE,
                channels=CHANNELS,
                dtype="int16",
                blocksize=CHUNK_SAMPLES,
            )
            stream.start()

            for _ in range(max_chunks):
                if not self._recording:
                    break

                data, overflowed = stream.read(CHUNK_SAMPLES)
                chunk = data.flatten()
                rms = np.sqrt(np.mean(chunk.astype(np.float32) ** 2))

                if rms > ENERGY_THRESHOLD:
                    energy_buffer.append(rms)
                    if len(energy_buffer) >= min_consecutive_energy:
                        speech_started = True
                        silence_chunks = 0
                        chunks.append(chunk)
                elif speech_started:
                    silence_chunks += 1
                    chunks.append(chunk)
                    energy_buffer.clear()
                    if silence_chunks >= max_silence_chunks:
                        break
                else:
                    energy_buffer.clear()

            stream.stop()
            stream.close()

        except Exception as e:
            logger.error("stt_recording_error", error=str(e))
            self._recording = False
            return ""

        self._recording = False

        if not chunks:
            logger.info("stt_no_speech_detected")
            return ""

        # Concatenate and transcribe
        audio = np.concatenate(chunks)
        duration_s = len(audio) / SAMPLE_RATE

        # Validate minimum speech duration
        if duration_s < MIN_SPEECH_DURATION_S:
            logger.info("stt_speech_too_short", duration_s=round(duration_s, 2))
            return ""

        logger.info(
            "stt_recording_complete",
            duration_s=round(duration_s, 2),
            samples=len(audio),
        )

        text = self.transcribe_audio(audio, SAMPLE_RATE)
        logger.info("stt_transcription_complete", text=text[:100])

        if self._on_transcription and text:
            self._on_transcription(text)

        return text

    def stop_recording(self) -> None:
        """Stop an active recording."""
        self._recording = False

    def unload(self) -> None:
        """Unload the model to free memory."""
        with self._model_lock:
            self._model = None
        logger.info("stt_model_unloaded")
