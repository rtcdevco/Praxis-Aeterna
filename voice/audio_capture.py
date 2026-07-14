"""Microphone input with a lightweight VAD (Voice Activity Detection) gate.

`sounddevice` is optional at import time, same pattern as STTEngine/TTSEngine —
this sandbox has no microphone to verify against, so `record()` degrades to a
clear "unavailable" result rather than raising. VAD itself is a real
computation (RMS energy against a threshold), not a stub — it's just simple
by design, since a heavier VAD model would be another optional dependency
this environment can't verify against real audio either.
"""
from __future__ import annotations

import math


class AudioCapture:
    def __init__(self, sample_rate: int = 16000, vad_threshold: float = 0.01):
        self.sample_rate = sample_rate
        self.vad_threshold = vad_threshold
        self.available = False
        self._sd = None
        try:
            import sounddevice as sd  # type: ignore

            self._sd = sd
            self.available = True
        except Exception:
            pass  # voice-optional: no mic/sounddevice in this environment

    def record(self, duration_seconds: float = 3.0) -> dict:
        if not self.available:
            return {
                "samples": None,
                "sample_rate": self.sample_rate,
                "error": "sounddevice not installed",
            }

        frame_count = int(duration_seconds * self.sample_rate)
        samples = self._sd.rec(
            frame_count, samplerate=self.sample_rate, channels=1, dtype="float32"
        )
        self._sd.wait()
        return {"samples": samples.reshape(-1).tolist(), "sample_rate": self.sample_rate}

    def is_speech(self, samples: list[float]) -> bool:
        """RMS energy vs. a fixed threshold. Real arithmetic on real samples —
        no hardware or optional dependency needed to call this directly, which
        is what makes it unit-testable without a microphone.
        """
        if not samples:
            return False
        mean_square = sum(s * s for s in samples) / len(samples)
        rms = math.sqrt(mean_square)
        return rms >= self.vad_threshold
