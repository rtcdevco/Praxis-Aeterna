"""VoiceOS — the facade the API server talks to.

Split out of the original combined voice/engines.py; now composes STT/TTS
with the rest of the pipeline (intent routing, wake-word gating, mic capture,
speaker playback) so a voice command actually flows end-to-end through this
one object instead of those modules sitting unused beside it.
"""
from __future__ import annotations

from pathlib import Path

from voice.audio_capture import AudioCapture
from voice.audio_playback import AudioPlayback
from voice.intent_router import IntentRouter
from voice.stt_engine import STTEngine
from voice.tts_engine import TTSEngine
from voice.wake_word import WakeWordDetector


class VoiceOS:
    def __init__(
        self,
        stt: STTEngine | None = None,
        tts: TTSEngine | None = None,
        intent_router: IntentRouter | None = None,
        capture: AudioCapture | None = None,
        playback: AudioPlayback | None = None,
    ):
        self.stt = stt or STTEngine()
        self.tts = tts or TTSEngine()
        self.intent_router = intent_router
        wake_phrase = intent_router.wake_phrase if intent_router else "hey fable"
        self.wake_word = WakeWordDetector(self.stt, wake_phrase=wake_phrase)
        self.capture = capture or AudioCapture()
        self.playback = playback or AudioPlayback()
        self.is_listening = False

    def status(self) -> dict:
        return {
            "stt_available": self.stt.available,
            "tts_available": self.tts.available,
            "listening": self.is_listening,
            "voice": self.tts.voice,
            "capture_available": self.capture.available,
            "playback_available": self.playback.available,
        }

    def handle_command(self, audio_path: str | Path) -> dict:
        """Transcribe audio and route it the same way a typed utterance is
        routed, via `IntentRouter` -> the shared `SkillRouter`. This is the
        one place `WakeWordDetector` and `IntentRouter` are actually called
        at runtime (previously they were unit-tested library code with no
        caller in the app).
        """
        transcription = self.stt.transcribe(audio_path)
        text = transcription.get("text", "")
        if not text:
            result = {"transcript": "", "wake_word_detected": False, "matched_skill": None}
            if "error" in transcription:
                result["error"] = transcription["error"]
            return result

        wake_word_detected = self.wake_word.detected_in_text(text)
        if self.intent_router is None:
            return {
                "transcript": text,
                "wake_word_detected": wake_word_detected,
                "matched_skill": None,
            }

        routed_text = self.intent_router.strip_wake_phrase(text)
        matched_skill = self.intent_router.route_transcript(routed_text)
        return {
            "transcript": text,
            "wake_word_detected": wake_word_detected,
            "matched_skill": matched_skill,
        }
