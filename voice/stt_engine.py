"""faster-whisper wrapper. 100% local, no API calls.

Split out of the original combined voice/engines.py so each engine matches
the Architecture Reference's one-module-per-concern voice pipeline.
"""
from __future__ import annotations

from pathlib import Path


class STTEngine:
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
