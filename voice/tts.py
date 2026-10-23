"""T.A.R.O. - Text-to-Speech engine (TASK-067).

ARCHITECTURE reference: section 9 (Voice Pipeline).
RULES reference: section 3, 10.
TASKS: TASK-067.

TTS pipeline:
  - Primary: edge-tts (online, high quality, async)
  - Fallback: pyttsx3 (offline, synchronous)
  - Playback queue with 1s get timeout for clean shutdown

Edge-tts falls back to pyttsx3 on any network error.
"""

from __future__ import annotations

import asyncio
import io
import tempfile
import time
import threading
from pathlib import Path
from typing import Any, Callable

from core.log.setup import get_logger

logger = get_logger(__name__)


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
TTS_ENGINE = _VOICE_CFG.get("tts_engine", "pyttsx3")
TTS_VOICE = _VOICE_CFG.get("tts_voice", None)
TTS_RATE = _VOICE_CFG.get("tts_rate", 150)


class TTSEngine:
    """Text-to-Speech engine using pyttsx3 (offline, lightweight).

    Acceptance (TASK-067):
    - Offline test uses pyttsx3
    - Supports custom voice expressions
    - Instant startup, no network dependency
    - Emotional tone mapping based on conversation context
    """

    def __init__(
        self,
        engine: str = TTS_ENGINE,
        voice: str | None = TTS_VOICE,
        rate: int = TTS_RATE,
        use_expressions: bool = True,
    ):
        self.engine_name = engine
        self.voice = voice
        self.rate = rate
        self.use_expressions = use_expressions
        self._queue: asyncio.Queue[str | None] = asyncio.Queue()
        self._running = False
        self._worker_task: asyncio.Task | None = None
        self._on_speak_start: Callable[[str], None] | None = None
        self._on_speak_end: Callable[[str], None] | None = None
        self._pyttsx3_engine = None
        self._pyttsx3_lock = threading.Lock()
        self._expression_manager = None
        # Emotional tone mapping
        self.emotion_rate_modifiers = {
            "energetic": 1.3,  # 30% faster
            "enthusiastic": 1.2,
            "thoughtful": 0.9,  # 10% slower
            "serious": 0.85,
            "calm": 0.95,
            "neutral": 1.0,
        }

    def on_speak(
        self,
        start: Callable[[str], None] | None = None,
        end: Callable[[str], None] | None = None,
    ) -> None:
        """Register callbacks for speech start/end events."""
        self._on_speak_start = start
        self._on_speak_end = end

    async def start(self) -> None:
        """Start the TTS playback worker."""
        if self._running:
            return
        self._running = True
        # Initialize expression manager if enabled
        if self.use_expressions:
            try:
                from voice.expressions import get_expression_manager
                self._expression_manager = get_expression_manager()
            except Exception as e:
                logger.debug("expression_manager_init_failed", error=str(e))
        self._worker_task = asyncio.get_running_loop().create_task(self._worker())
        logger.info("tts_started", engine=self.engine_name, voice=self.voice)

    async def stop(self) -> None:
        """Stop the TTS worker cleanly."""
        self._running = False
        await self._queue.put(None)  # Sentinel to unblock worker
        if self._worker_task:
            try:
                await asyncio.wait_for(self._worker_task, timeout=3.0)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                self._worker_task.cancel()
        if self._pyttsx3_engine:
            try:
                self._pyttsx3_engine.stop()
            except Exception:
                pass
        logger.info("tts_stopped")

    async def speak(self, text: str, emotion: str = "neutral") -> None:
        """Queue text for TTS playback with emotional tone."""
        if not text.strip():
            return
        # Attach emotion to the text using a marker
        emotion_text = f"[emotion:{emotion}] {text}"
        await self._queue.put(emotion_text)

    def _detect_emotion(self, text: str) -> str:
        """Simple emotion detection from text keywords."""
        text_lower = text.lower()
        
        # Energetic/enthusiastic keywords
        energetic_keywords = ["great", "awesome", "excited", "happy", "wonderful", "fantastic", "amazing"]
        if any(kw in text_lower for kw in energetic_keywords):
            return "energetic"
        
        # Serious/thoughtful keywords
        serious_keywords = ["important", "careful", "warning", "problem", "issue", "concern", "serious"]
        if any(kw in text_lower for kw in serious_keywords):
            return "serious"
        
        # Thoughtful/calm keywords
        thoughtful_keywords = ["think", "consider", "perhaps", "maybe", "interesting", "let me"]
        if any(kw in text_lower for kw in thoughtful_keywords):
            return "thoughtful"
        
        return "neutral"

    def _extract_emotion_and_text(self, marked_text: str) -> tuple[str, str]:
        """Extract emotion marker and clean text from marked text."""
        # Check for emotion marker format: [emotion:tag] text
        if marked_text.startswith("[emotion:") and "]" in marked_text:
            end_marker = marked_text.index("]")
            emotion = marked_text[9:end_marker].strip()
            text = marked_text[end_marker + 1:].strip()
            return emotion, text
        # Auto-detect emotion if no marker
        return self._detect_emotion(marked_text), marked_text

    async def speak_now(self, text: str) -> bool:
        """Speak text immediately (bypassing queue). Returns True on success."""
        return await self._synthesize_and_play(text)

    async def _worker(self) -> None:
        """Background worker: consume TTS queue and play audio."""
        while self._running:
            try:
                text = await asyncio.wait_for(self._queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue

            if text is None:
                break  # Shutdown sentinel

            await self._synthesize_and_play(text)

    async def _synthesize_and_play(self, marked_text: str) -> bool:
        """Synthesize and play a single utterance using pyttsx3. Returns True on success."""
        # Extract emotion and clean text
        emotion, text = self._extract_emotion_and_text(marked_text)
        
        # Apply emotion-based rate modifier
        rate_modifier = self.emotion_rate_modifiers.get(emotion, 1.0)
        adjusted_rate = int(self.rate * rate_modifier)
        
        if self._on_speak_start:
            self._on_speak_start(text)

        # Play pre-sentence expression if enabled
        if self._expression_manager and self.use_expressions:
            await self._play_expression()

        success = False
        try:
            success = await self._pyttsx3_speak(text, rate=adjusted_rate)
        except Exception as e:
            logger.error("tts_speak_error", error=str(e))

        # Play post-sentence expression if enabled
        if self._expression_manager and self.use_expressions and success:
            await self._play_expression(post_sentence=True)

        if self._on_speak_end:
            self._on_speak_end(text)

        return success

    async def _pyttsx3_speak(self, text: str, rate: int | None = None) -> bool:
        """Synthesize and play using pyttsx3 (offline, synchronous)."""
        try:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, self._pyttsx3_speak_sync, text, rate)
            return True
        except Exception as e:
            logger.error("pyttsx3_error", error=str(e))
            return False

    def _pyttsx3_speak_sync(self, text: str, rate: int | None = None) -> None:
        """Synchronous pyttsx3 speak (run in thread pool)."""
        import pyttsx3

        # Use provided rate or default
        speak_rate = rate if rate is not None else self.rate

        with self._pyttsx3_lock:
            try:
                if self._pyttsx3_engine is None:
                    self._pyttsx3_engine = pyttsx3.init()
                    # Set voice if specified
                    if self.voice:
                        voices = self._pyttsx3_engine.getProperty('voices')
                        for v in voices:
                            if self.voice.lower() in v.name.lower():
                                self._pyttsx3_engine.setProperty('voice', v.id)
                                break
                    # Set rate from config or parameter
                    self._pyttsx3_engine.setProperty("rate", speak_rate)
                else:
                    # Update rate if changed
                    self._pyttsx3_engine.setProperty("rate", speak_rate)
                    
                self._pyttsx3_engine.say(text)
                self._pyttsx3_engine.runAndWait()
            except Exception:
                # Engine might be in bad state, reinitialize
                self._pyttsx3_engine = None
                raise

    async def _play_audio_file(self, filepath: str) -> None:
        """Play an audio file. Uses platform-specific method."""
        import subprocess

        loop = asyncio.get_running_loop()

        def _play() -> None:
            # Use Windows presentationCore MediaPlayer for MP3/WAV playback
            norm_path = str(Path(filepath).resolve()).replace("'", "''")
            ps_script = (
                "Add-Type -AssemblyName presentationCore; "
                f"$m = New-Object System.Windows.Media.MediaPlayer; "
                f"$m.Open([System.Uri]'{norm_path}'); "
                "$m.Play(); "
                "Start-Sleep -Milliseconds 400; "
                "$maxWait = 600; "
                "while ($m.NaturalDuration.HasTimeSpan -and ($m.Position -lt $m.NaturalDuration.TimeSpan) -and ($maxWait -gt 0)) { "
                "    Start-Sleep -Milliseconds 100; "
                "    $maxWait--; "
                "} "
                "$m.Close();"
            )
            try:
                subprocess.run(
                    ["powershell", "-NoProfile", "-Command", ps_script],
                    capture_output=True,
                    timeout=30,
                )
            except Exception as e:
                logger.warning("audio_player_warning", error=str(e))

        await loop.run_in_executor(None, _play)

    async def _play_expression(self, post_sentence: bool = False) -> None:
        """Play a voice expression before or after the main response."""
        if not self._expression_manager:
            return

        try:
            exp = self._expression_manager.current_expression
            exp_path = self._expression_manager.assets_dir / exp.audio_file

            if exp_path.exists():
                logger.debug("playing_voice_expression", expression=exp.id, post_sentence=post_sentence)
                await self._play_audio_file(str(exp_path))
        except Exception as e:
            logger.debug("expression_playback_failed", error=str(e))


# Convenience function for quick speech
async def say(text: str, engine: str = TTS_ENGINE, voice: str = TTS_VOICE) -> bool:
    """Quick one-shot TTS. Returns True on success."""
    tts = TTSEngine(engine=engine, voice=voice)
    return await tts.speak_now(text)
