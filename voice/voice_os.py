"""VoiceOS — the facade the API server talks to.

Split out of the original combined voice/engines.py; now composes the two
engines plus intent routing and wake-word gating.
"""
from __future__ import annotations

from voice.stt_engine import STTEngine
from voice.tts_engine import TTSEngine


class VoiceOS:
    def __init__(self, stt: STTEngine | None = None, tts: TTSEngine | None = None):
        self.stt = stt or STTEngine()
        self.tts = tts or TTSEngine()
        self.is_listening = False

    def status(self) -> dict:
        return {
            "stt_available": self.stt.available,
            "tts_available": self.tts.available,
            "listening": self.is_listening,
            "voice": self.tts.voice,
        }
