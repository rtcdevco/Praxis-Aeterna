from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from config.settings import CONTEXT_TOKEN_BUDGET, LLM_EXECUTE_MAX_TOKENS, LLM_ROUTING_MAX_TOKENS
from core.context_budget import AnthropicTokenCounter, ContextBudget
from core.llm import SkillExecutionError, build_system_prompt, classify_route, execute_skill
from core.router import parse_context_files

router = APIRouter()

_ERROR_STATUS = {
    "rate_limited": 429,
    "timeout": 504,
    "connection_error": 504,
    "upstream_error": 502,
    "refused": 502,
}


@router.get("/skills")
def list_skills(request: Request) -> dict:
    return {"skills": request.app.state.router.skill_names}


class RouteRequest(BaseModel):
    utterance: str


def _load_context_files(skill_md_path: Path) -> list[tuple[str, str]]:
    skill_md_text = skill_md_path.read_text(encoding="utf-8")
    files = []
    for name in parse_context_files(skill_md_text):
        file_path = skill_md_path.parent / name
        if file_path.is_file():
            files.append((name, file_path.read_text(encoding="utf-8")))
    return files


def _route_and_assemble(request: Request, utterance: str):
    """Route (deterministic, then LLM fallback if configured) and assemble the
    matched skill's context package.

    Returns (matched_skill | None, routing_method, context_files, package | None).
    """
    skill_router = request.app.state.router
    client = request.app.state.anthropic_client

    matched = skill_router.route(utterance)
    routing_method = "deterministic" if matched else "none"

    if matched is None and client is not None:
        matched = classify_route(
            client,
            request.app.state.llm_model,
            utterance,
            skill_router.skill_names,
            LLM_ROUTING_MAX_TOKENS,
        )
        if matched is not None:
            routing_method = "llm_fallback"

    request.app.state.active_skill = matched
    if matched is None:
        request.app.state.last_context_package = None
        return None, routing_method, [], None

    skill_md_path = skill_router.skill_md_path(matched)
    skill_md_text = skill_md_path.read_text(encoding="utf-8")
    context_files = _load_context_files(skill_md_path)

    # Routing stays a zero-network-call operation: only build a real-counting
    # budget when a client is configured, right before it's actually needed.
    counter = AnthropicTokenCounter(client, request.app.state.llm_model) if client else None
    budget = ContextBudget(CONTEXT_TOKEN_BUDGET, counter=counter) if counter else request.app.state.context_budget
    package = budget.assemble(skill_md_text, context_files)
    request.app.state.last_context_package = package
    return matched, routing_method, context_files, package


@router.post("/skills/route")
def route_utterance(payload: RouteRequest, request: Request) -> dict:
    matched, routing_method, _, _ = _route_and_assemble(request, payload.utterance)
    return {"matched_skill": matched, "routing_method": routing_method}


class ExecuteRequest(BaseModel):
    utterance: str
    save_to_vault: bool = False
    vault_folder: str = "04-knowledge"
    vault_title: str | None = None


@router.post("/skills/execute")
def execute_utterance(payload: ExecuteRequest, request: Request) -> dict:
    matched, routing_method, context_files, package = _route_and_assemble(request, payload.utterance)

    if matched is None:
        return {
            "matched_skill": None,
            "routing_method": routing_method,
            "response": None,
            "usage": None,
            "saved_to_vault": None,
        }

    client = request.app.state.anthropic_client
    if client is None:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "llm_not_configured",
                "message": "ANTHROPIC_API_KEY is not set; skill execution is unavailable.",
            },
        )

    skill_router = request.app.state.router
    skill_md_text = skill_router.skill_md_path(matched).read_text(encoding="utf-8")
    system_prompt = build_system_prompt(skill_md_text, context_files, set(package.included_files))

    result = execute_skill(
        client,
        request.app.state.llm_model,
        system_prompt,
        payload.utterance,
        LLM_EXECUTE_MAX_TOKENS,
    )
    if isinstance(result, SkillExecutionError):
        detail = {"error": result.kind, "message": result.message}
        if result.retry_after is not None:
            detail["retry_after"] = result.retry_after
        raise HTTPException(status_code=_ERROR_STATUS[result.kind], detail=detail)

    saved = None
    if payload.save_to_vault:
        title = payload.vault_title or f"{matched}: {payload.utterance[:50]}"
        path = request.app.state.vault.save_note(result.text, payload.vault_folder, title)
        saved = {"path": str(path.relative_to(request.app.state.vault.vault_root))}

    return {
        "matched_skill": matched,
        "routing_method": routing_method,
        "response": result.text,
        "usage": {"input_tokens": result.input_tokens, "output_tokens": result.output_tokens},
        "saved_to_vault": saved,
    }
