# version: 1
# changed: 2026-07-09 | Claude | initial implementation
"""Observability endpoints: Prometheus-format metrics, composite health score
(with self-repair as a side effect of being polled), drift incidents, and the
version audit log.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse

from core.manifest import generate_manifest
from core.router import SkillRouter
from voice.voice_os import VoiceOS

router = APIRouter()


@router.get("/observability/metrics", response_class=PlainTextResponse)
def observability_metrics(request: Request) -> str:
    return request.app.state.metrics_collector.prometheus_text()


@router.get("/observability/incidents")
def observability_incidents(request: Request) -> dict:
    request.app.state.metrics_collector.sample_memory()
    detector = request.app.state.drift_detector
    detector.check_latency_drift()
    detector.check_error_clustering()
    return {"incidents": detector.recent_incidents()}


def _repair_brain(request: Request) -> None:
    app_state = request.app.state
    manifest = generate_manifest(app_state.skills_dir, app_state.manifest_path)
    app_state.router = SkillRouter(manifest, repo_root=app_state.skills_dir.parent)
    app_state.health_aggregator.router = app_state.router


def _repair_memory(request: Request) -> None:
    request.app.state.vault.scan_vault(force_rescan=True)


def _repair_voice(request: Request) -> None:
    app_state = request.app.state
    app_state.voice = VoiceOS()
    app_state.health_aggregator.voice_os = app_state.voice


@router.get("/health/score")
def health_score(request: Request) -> dict:
    app_state = request.app.state
    aggregator = app_state.health_aggregator
    trigger = app_state.repair_trigger

    components = aggregator.check_all()
    score = aggregator.composite_score(components)
    trigger.record_score(score)

    repair = None
    if trigger.should_repair():
        unhealthy = [c.name for c in components if not c.healthy]
        repair_actions = {
            "brain": lambda: _repair_brain(request),
            "memory": lambda: _repair_memory(request),
            "voice": lambda: _repair_voice(request),
        }
        for name, fn in repair_actions.items():
            fn.__name__ = f"reinit_{name}"  # dataclass/log wants a stable name, not <lambda>

        result = trigger.attempt_repair(
            unhealthy_components=unhealthy,
            repair_actions=repair_actions,
            score_before=score,
            score_after_fn=lambda: aggregator.composite_score(),
        )
        if result.triggered:
            repair = {
                "component": result.component,
                "action": result.action,
                "score_before": result.score_before,
                "score_after": result.score_after,
            }

    report = aggregator.report()
    report["repair"] = repair
    return report


@router.get("/audit/log")
def audit_log(request: Request) -> dict:
    return {"entries": request.app.state.version_audit.log()}
