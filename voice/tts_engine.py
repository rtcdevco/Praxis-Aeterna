"""Kokoro ONNX wrapper. Outputs 24kHz WAV.

Split out of the original combined voice/engines.py so each engine matches
the Architecture Reference's one-module-per-concern voice pipeline.
"""
from __future__ import annotations

from pathlib import Path


class TTSEngine:
    VOICES = ["af_bella", "af_nicole", "am_adam", "am_michael"]

    def __init__(self, voice: str = "af_bella", speed: float = 1.0,
                 model_path: str = "models/kokoro-v0_19.onnx",
                 voices_path: str = "models/voices.bin"):
        self.voice = voice
        self.speed = max(0.5, min(2.0, speed))
        self.available = False
        self._kokoro = None
        try:
            from kokoro_onnx import Kokoro  # type: ignore

            self._kokoro = Kokoro(model_path, voices_path)
            self.available = True
        except Exception:
            pass

    def synthesize(self, text: str, out_path: str | Path = "out.wav") -> dict:
        if not self.available:
            return {"path": None, "error": "kokoro-onnx not installed"}
        import soundfile as sf  # type: ignore

        samples, sample_rate = self._kokoro.create(text, voice=self.voice, speed=self.speed)
        sf.write(str(out_path), samples, sample_rate)
        return {"path": str(out_path), "sample_rate": sample_rate}
