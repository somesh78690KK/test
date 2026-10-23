"""T.A.R.O. - Audio worker (Voice Pipeline coordinator).

ARCHITECTURE reference: section 9 (Voice Pipeline).
RULES reference: section 3, 10.

Coordinates the full voice pipeline:
  mic -> VAD -> wake word -> STT -> input queue
  reply text -> TTS queue -> playback

Provides the single entry point for voice subsystem start/stop.
"""

from __future__ import annotations

import asyncio
from typing import Callable

from core.log.setup import get_logger

logger = get_logger(__name__)


class AudioWorker:
    """Coordinates wake word detection, STT recording, and TTS playback.

    Usage:
        worker = AudioWorker(on_input=lambda text: orchestrator.handle(text))
        await worker.start()
        ...
        await worker.stop()
    """

    def __init__(self, on_input: Callable[[str], None] | None = None, hands_free: bool = False):
        self.on_input = on_input
        self._tts = None
        self._stt = None
        self._wake = None
        self._running = False
        self._voice_enabled = True
        self._hands_free = hands_free

    async def start(self) -> None:
        """Start the full voice pipeline."""
        if self._running:
            return

        from voice.tts import TTSEngine
        from voice.stt import STTEngine
        from voice.wake_word import WakeWordDetector

        self._tts = TTSEngine()
        self._stt = STTEngine()
        self._wake = WakeWordDetector(on_wake=self._on_wake_detected, hands_free=self._hands_free)

        await self._tts.start()
        self._wake.start()

        self._running = True
        logger.info("audio_worker_started", hands_free=self._hands_free)

    async def stop(self) -> None:
        """Stop the voice pipeline cleanly."""
        self._running = False

        if self._wake:
            self._wake.stop()
        if self._tts:
            await self._tts.stop()
        if self._stt:
            self._stt.unload()

        logger.info("audio_worker_stopped")

    def _on_wake_detected(self) -> None:
        """Called when the wake word is detected. Starts recording."""
        if not self._running or not self._voice_enabled:
            return

        logger.info("voice_wake_triggered_recording")

        # Run STT in an asyncio task
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._record_and_dispatch())
        except RuntimeError:
            # No running event loop, run synchronously in thread
            import threading

            threading.Thread(
                target=self._record_sync, daemon=True
            ).start()

    async def _record_and_dispatch(self) -> None:
        """Record, transcribe, and dispatch to input handler."""
        if self._stt is None:
            return

        try:
            # Play acknowledgment sound using expression (not "Yes?" text)
            # Just a brief beep or the expression sound
            logger.info("voice_recording_started")

            text = await self._stt.record_and_transcribe()

            if text and self.on_input:
                logger.info("voice_input_received", text=text[:100])
                # Trigger the callback - this should display in chat via the HUD
                self.on_input(text)
        except Exception as e:
            logger.error("voice_record_dispatch_error", error=str(e))

    def _record_sync(self) -> None:
        """Synchronous fallback for recording when no event loop."""
        if self._stt is None:
            return
        try:
            text = self._stt._record_and_transcribe_sync(
                max_duration_s=8.0, silence_s=0.8
            )
            if text and self.on_input:
                self.on_input(text)
        except Exception as e:
            logger.error("voice_record_sync_error", error=str(e))

    async def say(self, text: str) -> None:
        """Speak text through TTS."""
        if self._tts:
            await self._tts.speak(text)

    def push_to_talk(self) -> None:
        """Trigger push-to-talk manually."""
        if self._wake:
            self._wake.trigger_push_to_talk()

    def set_voice_enabled(self, enabled: bool) -> None:
        """Enable or disable voice input."""
        self._voice_enabled = enabled
        logger.info("voice_enabled_changed", enabled=enabled)
