"""Face — FastAPI app serving the V.A.U.L.T. dashboard and its API."""

from __future__ import annotations

import time
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles

from config.settings import (
    CONTEXT_TOKEN_BUDGET,
    DRIFT_SIGMA_THRESHOLD,
    MANIFEST_PATH,
    METRICS_RETENTION_DAYS,
    OBSERVABILITY_DB_PATH,
    REPAIR_CONSECUTIVE_THRESHOLD,
    SKILLS_DIR,
    VAULT_DIR,
)
from core.context_budget import ContextBudget
from core.manifest import generate_manifest
from core.router import SkillRouter
from observability.drift_detector import DriftDetector
from observability.health_aggregator import HealthAggregator
from observability.metrics_collector import MetricsCollector
from observability.repair_trigger import RepairTrigger
from observability.version_audit import VersionAuditLog
from vault_connector.connector import VaultConnector
from voice.engines import VoiceOS

from .routes import graph, metrics, observability, skills, vault, voice

STATIC_DIR = Path(__file__).parent / "static"
REPO_ROOT = Path(__file__).resolve().parent.parent


def create_app(
    vault_dir: Path = VAULT_DIR,
    skills_dir: Path = SKILLS_DIR,
    manifest_path: Path = MANIFEST_PATH,
    observability_db_path: Path = OBSERVABILITY_DB_PATH,
) -> FastAPI:
    app = FastAPI(title="Fable 5 OS")

    manifest = generate_manifest(skills_dir, manifest_path)
    app.state.skills_dir = skills_dir
    app.state.manifest_path = manifest_path
    app.state.vault = VaultConnector(vault_dir)
    app.state.router = SkillRouter(manifest, repo_root=skills_dir.parent)
    app.state.context_budget = ContextBudget(CONTEXT_TOKEN_BUDGET)
    app.state.active_skill = None
    app.state.last_context_package = None
    app.state.voice = VoiceOS()

    app.state.metrics_collector = MetricsCollector(observability_db_path, METRICS_RETENTION_DAYS)
    app.state.drift_detector = DriftDetector(app.state.metrics_collector, DRIFT_SIGMA_THRESHOLD)
    app.state.version_audit = VersionAuditLog(app.state.metrics_collector._conn)
    app.state.health_aggregator = HealthAggregator(
        app.state.router, app.state.vault, app.state.voice, REPO_ROOT
    )
    app.state.repair_trigger = RepairTrigger(
        app.state.metrics_collector._conn, REPAIR_CONSECUTIVE_THRESHOLD
    )

    @app.middleware("http")
    async def record_metrics(request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000
        app.state.metrics_collector.record_request(
            path=request.url.path,
            method=request.method,
            duration_ms=duration_ms,
            status_code=response.status_code,
        )
        return response

    app.include_router(metrics.router, prefix="/api")
    app.include_router(skills.router, prefix="/api")
    app.include_router(graph.router, prefix="/api")
    app.include_router(voice.router, prefix="/api")
    app.include_router(vault.router, prefix="/api")
    app.include_router(observability.router, prefix="/api")

    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
    return app


app = create_app()
