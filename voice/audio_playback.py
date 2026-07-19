"""Speaker output for TTSEngine's synthesized WAV files.

`sounddevice` is optional at import time, same pattern as the rest of the
voice pipeline — no speakers to verify against in this environment, so
`play()` degrades to a clear "unavailable" result. Reuses `soundfile`
(already a voice-optional dependency via TTSEngine) to read the WAV back.
"""
from __future__ import annotations

from pathlib import Path


class AudioPlayback:
    def __init__(self):
        self.available = False
        self._sd = None
        try:
            import sounddevice as sd  # type: ignore

            self._sd = sd
            self.available = True
        except Exception:
            pass  # voice-optional: no speakers/sounddevice in this environment

    def play(self, wav_path: str | Path, blocking: bool = True) -> dict:
        if not self.available:
            return {"played": False, "error": "sounddevice not installed"}

        import soundfile as sf  # type: ignore

        data, sample_rate = sf.read(str(wav_path), dtype="float32")
        self._sd.play(data, sample_rate)
        if blocking:
            self._sd.wait()
        return {"played": True, "sample_rate": sample_rate}
