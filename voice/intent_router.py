"""Voice command routing — a thin adapter over the Brain's SkillRouter.

Deliberately does not reimplement routing logic: a voice transcript is just
text by the time it reaches here, so it's routed the exact same
regex-then-keyword way a typed utterance is (see core/router.py). This module
only adds what's specific to voice: reading `config/voice_patterns.json` for
the configured wake phrase.
"""
from __future__ import annotations

import json
from pathlib import Path

from core.router import SkillRouter

DEFAULT_WAKE_PHRASE = "hey fable"


def load_voice_patterns(path: str | Path) -> dict:
    """Reads config/voice_patterns.json. Returns the documented defaults if the
    file doesn't exist yet, rather than raising — voice patterns are optional
    configuration, not a required file.
    """
    path = Path(path)
    if not path.is_file():
        return {"wake_phrase": DEFAULT_WAKE_PHRASE, "commands": {}}
    return json.loads(path.read_text(encoding="utf-8"))


class IntentRouter:
    def __init__(self, skill_router: SkillRouter, wake_phrase: str = DEFAULT_WAKE_PHRASE):
        self.skill_router = skill_router
        self.wake_phrase = wake_phrase.lower()

    def route_transcript(self, text: str) -> str | None:
        return self.skill_router.route(text)

    def strip_wake_phrase(self, text: str) -> str:
        """If the transcript starts with the wake phrase, remove it before
        routing — "hey fable add a task" should route on "add a task", not
        the full utterance including the wake phrase.
        """
        lowered = text.lower()
        if lowered.startswith(self.wake_phrase):
            return text[len(self.wake_phrase):].strip()
        return text
