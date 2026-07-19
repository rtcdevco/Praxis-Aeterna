# version: 2
# changed: 2026-07-11 | Claude | update VoiceOS import path (voice.engines -> voice.voice_os)
"""Composite health score across the five pillars.

Adapted from the original spec's "poll all existing services": this app is a
single process, not five independently-running services, so there's nothing
to poll over the network. Instead each check calls the real in-process object
directly. `handoff` isn't a runtime component at all (it's deploy-time
tooling), so its "health" is a static file-presence check, not a live one —
that distinction is kept explicit in the result rather than faked as a live
check.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from core.router import SkillRouter
from vault_connector.connector import VaultConnector
from voice.voice_os import VoiceOS


@dataclass
class ComponentHealth:
    name: str
    healthy: bool
    detail: str


def check_brain(router: SkillRouter) -> ComponentHealth:
    try:
        healthy = len(router.skill_names) > 0
        detail = f"{len(router.skill_names)} skill(s) loaded" if healthy else "no skills loaded"
        return ComponentHealth("brain", healthy, detail)
    except Exception as exc:  # noqa: BLE001 - any failure here means "unhealthy", by design
        return ComponentHealth("brain", False, f"error: {exc}")


def check_memory(vault: VaultConnector) -> ComponentHealth:
    try:
        index = vault.scan_vault()
        return ComponentHealth("memory", True, f"{index.node_count} note(s) indexed")
    except Exception as exc:  # noqa: BLE001
        return ComponentHealth("memory", False, f"error: {exc}")


def check_face() -> ComponentHealth:
    # Tautologically healthy: this check only runs inside the face process
    # itself, so reaching this line already proves it's up. Kept as an
    # explicit component (not silently omitted) so the composite score's
    # denominator matches the five documented pillars.
    return ComponentHealth("face", True, "serving (in-process check)")


def check_voice(voice_os: VoiceOS) -> ComponentHealth:
    try:
        status = voice_os.status()
        # Structural health, not engine availability: STT/TTS being
        # unavailable is expected default behavior (optional deps), not a
        # failure. voice_engines_available is reported separately.
        return ComponentHealth("voice", True, f"listening={status['listening']}")
    except Exception as exc:  # noqa: BLE001
        return ComponentHealth("voice", False, f"error: {exc}")


def check_handoff(repo_root: Path) -> ComponentHealth:
    required = [
        repo_root / "deploy.sh",
        repo_root / "Dockerfile",
        repo_root / "deploy" / "fable5.service",
        repo_root / "deploy" / "scripts" / "reskin.sh",
    ]
    missing = [str(p.relative_to(repo_root)) for p in required if not p.is_file()]
    healthy = not missing
    detail = "all deploy assets present" if healthy else f"missing: {', '.join(missing)}"
    return ComponentHealth("handoff", healthy, detail)


class HealthAggregator:
    def __init__(
        self, router: SkillRouter, vault: VaultConnector, voice_os: VoiceOS, repo_root: Path
    ):
        self.router = router
        self.vault = vault
        self.voice_os = voice_os
        self.repo_root = repo_root

    def check_all(self) -> list[ComponentHealth]:
        return [
            check_brain(self.router),
            check_memory(self.vault),
            check_face(),
            check_voice(self.voice_os),
            check_handoff(self.repo_root),
        ]

    def composite_score(self, components: list[ComponentHealth] | None = None) -> float:
        components = components if components is not None else self.check_all()
        if not components:
            return 0.0
        return sum(1 for c in components if c.healthy) / len(components)

    def report(self) -> dict:
        components = self.check_all()
        try:
            status = self.voice_os.status()
            voice_engines_available = {
                "stt": status["stt_available"],
                "tts": status["tts_available"],
            }
        except Exception:  # noqa: BLE001 - already reflected as unhealthy above; don't crash the report
            voice_engines_available = {"stt": None, "tts": None}
        return {
            "score": self.composite_score(components),
            "components": {c.name: {"healthy": c.healthy, "detail": c.detail} for c in components},
            "voice_engines_available": voice_engines_available,
        }
