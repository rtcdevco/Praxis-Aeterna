import json
import sys
import types

from core.manifest import generate_manifest
from core.router import SkillRouter
from voice.audio_capture import AudioCapture
from voice.audio_playback import AudioPlayback
from voice.intent_router import DEFAULT_WAKE_PHRASE, IntentRouter, load_voice_patterns
from voice.stt_engine import STTEngine
from voice.wake_word import WakeWordDetector

# --- audio_capture ---------------------------------------------------------

def test_audio_capture_unavailable_without_dep():
    capture = AudioCapture()
    assert capture.available is False
    result = capture.record(duration_seconds=1.0)
    assert result["samples"] is None
    assert result["error"] == "sounddevice not installed"


def test_audio_capture_is_speech_above_threshold():
    capture = AudioCapture(vad_threshold=0.01)
    loud_samples = [0.5, -0.5, 0.5, -0.5]
    assert capture.is_speech(loud_samples) is True


def test_audio_capture_is_speech_below_threshold():
    capture = AudioCapture(vad_threshold=0.5)
    quiet_samples = [0.001, -0.001, 0.001, -0.001]
    assert capture.is_speech(quiet_samples) is False


def test_audio_capture_is_speech_empty_samples():
    capture = AudioCapture()
    assert capture.is_speech([]) is False


def test_audio_capture_record_happy_path(monkeypatch):
    class FakeArray:
        def reshape(self, *args):
            return self

        def tolist(self):
            return [0.1, 0.2, 0.3]

    class FakeSoundDevice:
        def rec(self, frames, samplerate, channels, dtype):
            return FakeArray()

        def wait(self):
            pass

    fake_module = types.ModuleType("sounddevice")
    fake_sd = FakeSoundDevice()
    fake_module.rec = fake_sd.rec
    fake_module.wait = fake_sd.wait
    monkeypatch.setitem(sys.modules, "sounddevice", fake_module)

    capture = AudioCapture(sample_rate=16000)
    assert capture.available is True
    result = capture.record(duration_seconds=1.0)
    assert result == {"samples": [0.1, 0.2, 0.3], "sample_rate": 16000}


# --- audio_playback ---------------------------------------------------------

def test_audio_playback_unavailable_without_dep():
    playback = AudioPlayback()
    assert playback.available is False
    result = playback.play("out.wav")
    assert result == {"played": False, "error": "sounddevice not installed"}


def test_audio_playback_play_happy_path(monkeypatch, tmp_path):
    class FakeSoundDevice:
        def play(self, data, sample_rate):
            self.played_with = (data, sample_rate)

        def wait(self):
            pass

    fake_sd_module = types.ModuleType("sounddevice")
    fake_sd = FakeSoundDevice()
    fake_sd_module.play = fake_sd.play
    fake_sd_module.wait = fake_sd.wait
    monkeypatch.setitem(sys.modules, "sounddevice", fake_sd_module)

    fake_sf_module = types.ModuleType("soundfile")
    fake_sf_module.read = lambda path, dtype="float32": ([0.1, 0.2], 24000)
    monkeypatch.setitem(sys.modules, "soundfile", fake_sf_module)

    playback = AudioPlayback()
    assert playback.available is True
    result = playback.play(tmp_path / "out.wav")
    assert result == {"played": True, "sample_rate": 24000}


# --- intent_router -----------------------------------------------------------

def _make_router(tmp_path):
    skills_dir = tmp_path / "skills"
    skill_dir = skills_dir / "productivity"
    skill_dir.mkdir(parents=True)
    skill_md = (
        '---\nintent_patterns:\n  - "\\\\btask\\\\b"\nkeywords: [task]\npriority: 0\n---\n# Skill\n'
    )
    (skill_dir / "SKILL.md").write_text(skill_md, encoding="utf-8")
    manifest = generate_manifest(skills_dir, tmp_path / "skills_manifest.json")
    return SkillRouter(manifest, repo_root=tmp_path)


def test_intent_router_routes_transcript(tmp_path):
    skill_router = _make_router(tmp_path)
    intent_router = IntentRouter(skill_router)
    assert intent_router.route_transcript("add a task") == "productivity"


def test_intent_router_no_match(tmp_path):
    skill_router = _make_router(tmp_path)
    intent_router = IntentRouter(skill_router)
    assert intent_router.route_transcript("completely unrelated") is None


def test_intent_router_strips_wake_phrase(tmp_path):
    skill_router = _make_router(tmp_path)
    intent_router = IntentRouter(skill_router, wake_phrase="hey fable")
    assert intent_router.strip_wake_phrase("hey fable add a task") == "add a task"


def test_intent_router_strip_wake_phrase_noop_without_prefix(tmp_path):
    skill_router = _make_router(tmp_path)
    intent_router = IntentRouter(skill_router, wake_phrase="hey fable")
    assert intent_router.strip_wake_phrase("add a task") == "add a task"


def test_load_voice_patterns_missing_file_returns_defaults(tmp_path):
    patterns = load_voice_patterns(tmp_path / "does-not-exist.json")
    assert patterns == {"wake_phrase": DEFAULT_WAKE_PHRASE, "commands": {}}


def test_load_voice_patterns_reads_real_file(tmp_path):
    path = tmp_path / "voice_patterns.json"
    path.write_text(json.dumps({"wake_phrase": "yo fable", "commands": {"ops": ["status"]}}))
    patterns = load_voice_patterns(path)
    assert patterns == {"wake_phrase": "yo fable", "commands": {"ops": ["status"]}}


def test_load_real_repo_voice_patterns_file():
    from config.settings import VOICE_PATTERNS_PATH

    patterns = load_voice_patterns(VOICE_PATTERNS_PATH)
    assert patterns["wake_phrase"] == "hey fable"
    assert "productivity" in patterns["commands"]


# --- wake_word ---------------------------------------------------------------

def test_wake_word_detected_in_text():
    detector = WakeWordDetector(STTEngine(), wake_phrase="hey fable")
    assert detector.detected_in_text("hey fable what's up") is True
    assert detector.detected_in_text("completely unrelated") is False


def test_wake_word_detected_unavailable_without_stt_dep():
    detector = WakeWordDetector(STTEngine(), wake_phrase="hey fable")
    result = detector.detected("clip.wav")
    assert result == {"detected": False, "error": "faster-whisper not installed"}


def test_wake_word_detected_with_mocked_stt():
    class FakeSTT:
        available = True

        def transcribe(self, path):
            return {"text": "hey fable start listening"}

    detector = WakeWordDetector(FakeSTT(), wake_phrase="hey fable")
    result = detector.detected("clip.wav")
    assert result == {"detected": True, "text": "hey fable start listening"}
