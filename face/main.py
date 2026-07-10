"""Face — FastAPI app serving the V.A.U.L.T. dashboard and its API."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from config.settings import CONTEXT_TOKEN_BUDGET, LLM_MODEL, MANIFEST_PATH, SKILLS_DIR, VAULT_DIR
from core.context_budget import ContextBudget
from core.llm import build_client
from core.manifest import generate_manifest
from core.router import SkillRouter
from vault_connector.connector import VaultConnector

from .routes import graph, metrics, skills, vault, voice

STATIC_DIR = Path(__file__).parent / "static"

# Sentinel so tests can force anthropic_client=None (the "not configured" path)
# independent of whatever ANTHROPIC_API_KEY happens to be set in the real
# environment — plain None as the default wouldn't let a test distinguish
# "not passed" from "explicitly disabled".
_UNSET = object()


def create_app(
    vault_dir: Path = VAULT_DIR,
    skills_dir: Path = SKILLS_DIR,
    manifest_path: Path = MANIFEST_PATH,
    anthropic_client: object = _UNSET,
) -> FastAPI:
    app = FastAPI(title="Fable 5 OS")

    manifest = generate_manifest(skills_dir, manifest_path)
    app.state.vault = VaultConnector(vault_dir)
    app.state.router = SkillRouter(manifest, repo_root=skills_dir.parent)
    app.state.context_budget = ContextBudget(CONTEXT_TOKEN_BUDGET)
    app.state.active_skill = None
    app.state.last_context_package = None
    app.state.anthropic_client = build_client() if anthropic_client is _UNSET else anthropic_client
    app.state.llm_model = LLM_MODEL

    app.include_router(metrics.router, prefix="/api")
    app.include_router(skills.router, prefix="/api")
    app.include_router(graph.router, prefix="/api")
    app.include_router(voice.router, prefix="/api")
    app.include_router(vault.router, prefix="/api")

    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
    return app


app = create_app()
