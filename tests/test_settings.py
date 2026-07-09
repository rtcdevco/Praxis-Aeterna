import importlib

import pytest

import config.settings as settings


def test_require_anthropic_api_key_raises_clear_error_when_missing(monkeypatch):
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", None)
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY is not set"):
        settings.require_anthropic_api_key()


def test_require_anthropic_api_key_returns_value_when_set(monkeypatch):
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "sk-ant-test")
    assert settings.require_anthropic_api_key() == "sk-ant-test"


def test_fable5_model_reads_env_var(monkeypatch):
    monkeypatch.setenv("FABLE5_MODEL", "claude-opus-4-8")
    importlib.reload(settings)
    assert settings.FABLE5_MODEL == "claude-opus-4-8"
    # restore default for any tests that import settings afterward
    monkeypatch.delenv("FABLE5_MODEL", raising=False)
    importlib.reload(settings)
