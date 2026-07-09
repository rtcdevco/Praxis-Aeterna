"""Voice status + STT/TTS endpoints, backed by voice.engines.VoiceOS.

Both engines report `available: False` when their optional dependency isn't
installed — every route here degrades to a clear JSON error instead of a
500 in that case, so the dashboard and API stay usable text-only.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import APIRouter, Request, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

router = APIRouter()


@router.get("/voice/status")
def voice_status(request: Request) -> dict:
    voice_os = request.app.state.voice
    status = voice_os.status()
    return {
        "stt": "available" if status["stt_available"] else "unavailable",
        "tts": "available" if status["tts_available"] else "unavailable",
        "state": "listening" if status["listening"] else "idle",
        "voice": status["voice"],
    }


@router.post("/voice/transcribe")
async def transcribe(request: Request, file: UploadFile) -> dict:
    voice_os = request.app.state.voice
    if not voice_os.stt.available:
        return {"text": "", "error": "faster-whisper not installed"}

    suffix = Path(file.filename or "audio").suffix
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name

    return voice_os.stt.transcribe(tmp_path)


class SynthesizeRequest(BaseModel):
    text: str


@router.post("/voice/synthesize")
def synthesize(payload: SynthesizeRequest, request: Request):
    voice_os = request.app.state.voice
    if not voice_os.tts.available:
        return {"path": None, "error": "kokoro-onnx not installed"}

    out_path = Path(tempfile.gettempdir()) / f"fable5-tts-{id(payload)}.wav"
    result = voice_os.tts.synthesize(payload.text, out_path=out_path)
    if result.get("path") is None:
        return result
    return FileResponse(result["path"], media_type="audio/wav")
