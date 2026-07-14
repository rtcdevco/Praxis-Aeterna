"""Wake-word detection.

Deliberately does not add a dedicated wake-word engine dependency (e.g. a
proprietary keyword-spotting SDK): this environment can't verify one against
real audio hardware any more than it can faster-whisper or Kokoro, and it
would be an unjustified new dependency (see the "no new deps without
justification" constraint from the observability build). Instead this reuses
the STT engine that's already part of the voice pipeline — transcribe a short
buffer, check whether the wake phrase appears in the text. Simpler, no new
dependency, and honestly scoped to what's actually verifiable here.
"""
from __future__ import annotations

from pathlib import Path

from voice.stt_engine import STTEngine


class WakeWordDetector:
    def __init__(self, stt_engine: STTEngine, wake_phrase: str = "hey fable"):
        self.stt_engine = stt_engine
        self.wake_phrase = wake_phrase.lower()

    def detected_in_text(self, text: str) -> bool:
        return self.wake_phrase in text.lower()

    def detected(self, audio_path: str | Path) -> dict:
        if not self.stt_engine.available:
            return {"detected": False, "error": "faster-whisper not installed"}
        result = self.stt_engine.transcribe(audio_path)
        text = result.get("text", "")
        return {"detected": self.detected_in_text(text), "text": text}
