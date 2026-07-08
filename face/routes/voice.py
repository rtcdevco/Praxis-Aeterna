"""Voice status — a static stub. Real STT/TTS wiring is a separate, later phase:
this sandbox has no mic/speakers to verify it against, so this route only
reports a fixed "not configured" state rather than a real check.
"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/voice/status")
def voice_status() -> dict:
    return {
        "stt": "unavailable",
        "tts": "unavailable",
        "state": "idle",
        "reason": "voice phase not yet implemented",
    }
