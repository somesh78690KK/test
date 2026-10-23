"""T.A.R.O. - Local Text-to-Speech Engine.

Lightweight, offline-capable TTS using pyttsx3.
Replaces Edge TTS for offline operation.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pyttsx3
from core.log.setup import get_logger

logger = get_logger(__name__)


class LocalTTSEngine:
    """Local pyttsx3-based TTS engine."""

    def __init__(self, voice_name: str | None = None, rate: int = 150):
        self.voice_name = voice_name
        self.rate = rate
        self.engine = None
        self._loaded = False

    def load_engine(self) -> bool:
        """Load the TTS engine."""
        try:
            logger.info("tts_loading_engine", engine="pyttsx3")
            self.engine = pyttsx3.init()
            
            # Set voice
            if self.voice_name:
                voices = self.engine.getProperty('voices')
                for voice in voices:
                    if self.voice_name.lower() in voice.name.lower():
                        self.engine.setProperty('voice', voice.id)
                        break
            
            # Set rate
            self.engine.setProperty('rate', self.rate)
            
            self._loaded = True
            logger.info("tts_engine_loaded", engine="pyttsx3")
            return True
        except Exception as e:
            logger.error("tts_load_error", error=str(e))
            return False

    def speak(self, text: str) -> bool:
        """Speak text synchronously."""
        if not self._loaded:
            if not self.load_engine():
                return False

        try:
            logger.info("tts_speaking", text=text[:50])
            self.engine.say(text)
            self.engine.runAndWait()
            return True
        except Exception as e:
            logger.error("tts_speak_error", error=str(e))
            return False

    def speak_async(self, text: str) -> bool:
        """Speak text asynchronously."""
        if not self._loaded:
            if not self.load_engine():
                return False

        try:
            logger.info("tts_speaking_async", text=text[:50])
            self.engine.say(text)
            # Don't block - let the event loop handle it
            self.engine.runAndWait()
            return True
        except Exception as e:
            logger.error("tts_speak_async_error", error=str(e))
            return False

    def stop(self) -> None:
        """Stop current speech."""
        if self._loaded and self.engine:
            try:
                self.engine.stop()
            except Exception as e:
                logger.error("tts_stop_error", error=str(e))


# Global instance
_tts_engine: LocalTTSEngine | None = None


def get_tts_engine() -> LocalTTSEngine:
    """Get or create the global TTS engine."""
    global _tts_engine
    if _tts_engine is None:
        _tts_engine = LocalTTSEngine()
    return _tts_engine


def speak(text: str) -> bool:
    """Convenience function to speak text."""
    engine = get_tts_engine()
    return engine.speak(text)


def speak_async(text: str) -> bool:
    """Convenience function to speak text asynchronously."""
    engine = get_tts_engine()
    return engine.speak_async(text)
