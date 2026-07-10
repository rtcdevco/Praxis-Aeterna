import sys
import types

from voice.engines import STTEngine, TTSEngine, VoiceOS


def test_stt_unavailable_without_dep():
    engine = STTEngine()
    assert engine.available is False
    result = engine.transcribe("some.wav")
    assert result == {"text": "", "error": "faster-whisper not installed"}


def test_tts_unavailable_without_dep():
    engine = TTSEngine()
    assert engine.available is False
    result = engine.synthesize("hello")
    assert result == {"path": None, "error": "kokoro-onnx not installed"}


def test_voice_os_status_reports_unavailable_by_default():
    voice_os = VoiceOS()
    status = voice_os.status()
    assert status == {
        "stt_available": False,
        "tts_available": False,
        "listening": False,
        "voice": "af_bella",
    }


def test_stt_transcribe_happy_path(monkeypatch):
    class FakeWord:
        def __init__(self, word, start, end):
            self.word = word
            self.start = start
            self.end = end

    class FakeSegment:
        def __init__(self, text, words):
            self.text = text
            self.words = words

    class FakeInfo:
        language = "en"

    class FakeWhisperModel:
        def __init__(self, *args, **kwargs):
            pass

        def transcribe(self, path, language=None, vad_filter=True, word_timestamps=True):
            words = [FakeWord("hello", 0.0, 0.5), FakeWord("world", 0.5, 1.0)]
            segments = [FakeSegment("hello world", words)]
            return segments, FakeInfo()

    fake_module = types.ModuleType("faster_whisper")
    fake_module.WhisperModel = FakeWhisperModel
    monkeypatch.setitem(sys.modules, "faster_whisper", fake_module)

    engine = STTEngine()
    assert engine.available is True
    result = engine.transcribe("some.wav")
    assert result["text"] == "hello world"
    assert result["language"] == "en"
    assert result["words"] == [
        {"word": "hello", "start": 0.0, "end": 0.5},
        {"word": "world", "start": 0.5, "end": 1.0},
    ]


def test_tts_synthesize_happy_path(monkeypatch, tmp_path):
    class FakeKokoro:
        def __init__(self, *args, **kwargs):
            pass

        def create(self, text, voice="af_bella", speed=1.0):
            return [0.0, 0.1, 0.2], 24000

    fake_kokoro_module = types.ModuleType("kokoro_onnx")
    fake_kokoro_module.Kokoro = FakeKokoro
    monkeypatch.setitem(sys.modules, "kokoro_onnx", fake_kokoro_module)

    written = {}

    def fake_write(path, samples, sample_rate):
        written["path"] = path
        written["samples"] = samples
        written["sample_rate"] = sample_rate

    fake_sf_module = types.ModuleType("soundfile")
    fake_sf_module.write = fake_write
    monkeypatch.setitem(sys.modules, "soundfile", fake_sf_module)

    engine = TTSEngine()
    assert engine.available is True
    out_path = tmp_path / "out.wav"
    result = engine.synthesize("hello", out_path=out_path)
    assert result == {"path": str(out_path), "sample_rate": 24000}
    assert written["path"] == str(out_path)


def test_tts_speed_clamped():
    assert TTSEngine(speed=10.0).speed == 2.0
    assert TTSEngine(speed=0.01).speed == 0.5
