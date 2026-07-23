"""Voice status + STT/TTS endpoints, backed by voice.voice_os.VoiceOS.

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

from core.session import DEFAULT_SESSION_ID

from .skills import load_context_files

router = APIRouter()


def _set_active_skill(
    request: Request, matched_skill: str | None, session_id: str = DEFAULT_SESSION_ID
) -> None:
    """Same context-manager update `/skills/route` does for a typed
    utterance, applied to a skill matched from a voice transcript so both
    entry points leave the session in the same state.
    """
    if matched_skill is None:
        return
    context_manager = request.app.state.context_manager
    skill_router = request.app.state.router
    context_manager.set_active_skill(session_id, matched_skill)
    skill_md_path = skill_router.skill_md_path(matched_skill)
    skill_md_text = skill_md_path.read_text(encoding="utf-8")
    context_manager.assemble(
        session_id, skill_md_text, load_context_files(skill_md_path)
    )


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


@router.post("/voice/command")
async def voice_command(
    request: Request, file: UploadFile, session_id: str = DEFAULT_SESSION_ID
) -> dict:
    """Transcribe an uploaded audio clip and route it exactly like a typed
    utterance — the real entry point for `IntentRouter`/`WakeWordDetector`,
    which previously had no caller anywhere in the app.

    `session_id` is a query param, not a body/form field — the body here is
    already the multipart file upload. Unlike `/skills/route`, this is the
    only place `session_id` can go; a JSON or form field named `session_id`
    sent alongside `file` is silently dropped, not rejected.
    """
    voice_os = request.app.state.voice
    if not voice_os.stt.available:
        return {"transcript": "", "matched_skill": None, "error": "faster-whisper not installed"}

    suffix = Path(file.filename or "audio").suffix
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name

    result = voice_os.handle_command(tmp_path)
    _set_active_skill(request, result.get("matched_skill"), session_id)
    return result


@router.post("/voice/listen")
def listen(
    request: Request, duration_seconds: float = 3.0, session_id: str = DEFAULT_SESSION_ID
) -> dict:
    """Capture a short clip from the mic, VAD-gate it, and route it through
    the same command pipeline as `/voice/command`. The real entry point for
    `AudioCapture`/`AudioPlayback`; degrades to a clear "unavailable" result
    in any environment without a mic/speakers, same pattern as the rest of
    the voice pillar.

    `session_id` is a query param, same as `duration_seconds` — see
    `/voice/command`'s docstring for why the voice routes use query params
    instead of `/skills/route`'s JSON body field.
    """
    voice_os = request.app.state.voice
    capture = voice_os.capture
    if not capture.available:
        return {
            "speech_detected": False,
            "matched_skill": None,
            "error": "sounddevice not installed",
        }

    recording = capture.record(duration_seconds=duration_seconds)
    if recording.get("samples") is None:
        return {"speech_detected": False, "matched_skill": None, "error": recording["error"]}

    if not capture.is_speech(recording["samples"]):
        return {"speech_detected": False, "matched_skill": None}

    if not voice_os.stt.available:
        return {
            "speech_detected": True,
            "matched_skill": None,
            "error": "faster-whisper not installed",
        }

    import soundfile as sf  # type: ignore

    clip_path = Path(tempfile.gettempdir()) / f"fable5-capture-{id(recording)}.wav"
    sf.write(str(clip_path), recording["samples"], recording["sample_rate"])

    result = voice_os.handle_command(clip_path)
    result["speech_detected"] = True
    _set_active_skill(request, result.get("matched_skill"), session_id)

    if result.get("matched_skill") and voice_os.tts.available and voice_os.playback.available:
        synth = voice_os.tts.synthesize(f"Routed to {result['matched_skill']}")
        if synth.get("path"):
            voice_os.playback.play(synth["path"])
            result["spoken_response"] = True

    return result
