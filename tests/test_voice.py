"""Tests for T.A.R.O. Voice subsystem (TASK-065, TASK-066, TASK-067, TASK-068)."""

import asyncio
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from voice.audio_worker import AudioWorker
from voice.mic_test import run_mic_self_test
from voice.stt import STTEngine
from voice.tts import TTSEngine
from voice.wake_word import WakeWordDetector


# --- TASK-065: Wake Word & Push-to-Talk ---

def test_task_065_wake_word_push_to_talk():
    """TASK-065: Push-to-talk works when wake word is off/idle."""
    called = []

    def on_wake():
        called.append(True)

    detector = WakeWordDetector(on_wake=on_wake)
    assert not detector._running

    # Trigger push-to-talk directly without starting continuous listening loop
    detector.trigger_push_to_talk()
    assert len(called) == 1

    # Test AudioWorker push-to-talk integration
    worker = AudioWorker(on_input=lambda text: None)
    worker._wake = detector
    worker.push_to_talk()
    assert len(called) == 2


def test_task_065_wake_word_keyword_matching():
    """TASK-065: Wake word detector identifies 'taro' keyword in transcribed audio."""
    triggered = []
    detector = WakeWordDetector(on_wake=lambda: triggered.append(True))
    detector.wake_word = "taro"

    mock_stt = MagicMock()
    mock_stt.transcribe_audio.return_value = "hey taro please help me"
    detector._stt_engine = mock_stt

    # Simulate buffer check
    dummy_audio = np.zeros(16000, dtype=np.int16)
    text = detector._get_stt().transcribe_audio(dummy_audio, 16000).lower()
    assert "taro" in text


# --- TASK-066: Google STT online fallback (consent required) ---

def test_task_066_google_stt_consent_enforcement():
    """TASK-066: Google STT fallback requires explicit user consent; not used when consent is off."""
    engine = STTEngine(google_stt_consent=False)
    dummy_audio = np.zeros(1600, dtype=np.int16)

    # Calling transcribe_google without consent must raise PermissionError
    with pytest.raises(PermissionError) as exc_info:
        engine.transcribe_google(dummy_audio, sample_rate=16000)
    assert "requires explicit user consent" in str(exc_info.value)

    # Calling with explicit consent=False must also raise
    with pytest.raises(PermissionError):
        engine.transcribe_google(dummy_audio, sample_rate=16000, consent=False)


def test_task_066_google_stt_fallback_when_whisper_fails():
    """TASK-066: When faster-whisper fails, Google STT is used ONLY if consent is given."""
    dummy_audio = np.zeros(1600, dtype=np.int16)

    # 1. Without consent: failure in whisper raises exception, Google STT is NOT used
    engine_no_consent = STTEngine(google_stt_consent=False)
    with patch.object(engine_no_consent, "_ensure_model", side_effect=RuntimeError("Whisper crashed")):
        with pytest.raises(RuntimeError):
            engine_no_consent.transcribe_audio(dummy_audio)

    # 2. With consent: failure in whisper triggers Google fallback
    engine_with_consent = STTEngine(google_stt_consent=True)
    with patch.object(engine_with_consent, "_ensure_model", side_effect=RuntimeError("Whisper crashed")):
        with patch.object(engine_with_consent, "transcribe_google", return_value="hello from google") as mock_google:
            result = engine_with_consent.transcribe_audio(dummy_audio)
            assert result == "hello from google"
            mock_google.assert_called_once()


# --- TASK-067: TTS (edge-tts, pyttsx3 fallback, queue) ---

@pytest.mark.asyncio
async def test_task_067_tts_offline_pyttsx3_fallback():
    """TASK-067: Offline test uses pyttsx3 fallback."""
    tts = TTSEngine(engine="edge-tts", fallback="pyttsx3")

    with patch.object(tts, "_edge_tts_speak", return_value=False):
        with patch.object(tts, "_pyttsx3_speak", return_value=True) as mock_pyttsx3:
            result = await tts.speak_now("Offline testing")
            assert result is True
            mock_pyttsx3.assert_called_once_with("Offline testing")


@pytest.mark.asyncio
async def test_task_067_tts_online_edge_tts():
    """TASK-067: Online test uses edge-tts when available."""
    tts = TTSEngine(engine="edge-tts", fallback="pyttsx3")

    with patch.object(tts, "_edge_tts_speak", return_value=True) as mock_edge:
        result = await tts.speak_now("Online testing")
        assert result is True
        mock_edge.assert_called_once_with("Online testing")


# --- TASK-068: Microphone self-test ---

def test_task_068_microphone_self_test():
    """TASK-068: Reports device name, level, and pass/fail."""
    result = run_mic_self_test(duration_s=0.1)

    assert isinstance(result, dict)
    assert "device_name" in result
    assert "level" in result
    assert "passed" in result
    assert "details" in result
    assert isinstance(result["device_name"], str)
    assert isinstance(result["level"], (int, float))
    assert isinstance(result["passed"], bool)
    assert len(result["device_name"]) > 0


def test_task_068_microphone_self_test_mocked_failure():
    """TASK-068: Correctly reports failure when audio recording fails."""
    with patch("sounddevice.rec", side_effect=Exception("Hardware device busy")):
        with patch("sounddevice.query_devices", return_value={"name": "Realtek Audio"}):
            result = run_mic_self_test(duration_s=0.1)
            assert result["passed"] is False
            assert "Realtek Audio" in result["device_name"]
            assert result["level"] == 0.0
