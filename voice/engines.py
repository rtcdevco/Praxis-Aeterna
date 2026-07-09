"""Local voice pipeline: faster-whisper (STT) + Kokoro (TTS).

Both engines are optional at import time — the system runs text-only
if voice deps aren't installed, and reports status to the dashboard.

Pipeline: Mic -> AudioCapture(VAD) -> STT -> intent router -> Claude -> TTS -> speaker
"""
from __future__ import annotations

from pathlib import Path


class STTEngine:
    """faster-whisper wrapper. 100% local, no API calls."""

    def __init__(self, model_size: str = "base", language: str | None = None):
        self.model_size = model_size
        self.language = language
        self.available = False
        self._model = None
        try:
            from faster_whisper import WhisperModel  # type: ignore

            self._model = WhisperModel(model_size, device="auto", compute_type="auto")
            self.available = True
        except Exception:
            pass  # voice-optional: dashboard shows STT offline

    def transcribe(self, audio_path: str | Path) -> dict:
        if not self.available:
            return {"text": "", "error": "faster-whisper not installed"}
        segments, info = self._model.transcribe(
            str(audio_path), language=self.language, vad_filter=True,
            word_timestamps=True,
        )
        words, chunks = [], []
        for seg in segments:
            chunks.append(seg.text)
            for w in seg.words or []:
                words.append({"word": w.word, "start": w.start, "end": w.end})
        return {"text": "".join(chunks).strip(), "language": info.language, "words": words}


class TTSEngine:
    """Kokoro ONNX wrapper. Outputs 24kHz WAV."""

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


class VoiceOS:
    """Facade the API server talks to."""

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
