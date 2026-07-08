from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request
from pydantic import BaseModel

from core.router import parse_context_files

router = APIRouter()


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


@router.post("/skills/route")
def route_utterance(payload: RouteRequest, request: Request) -> dict:
    skill_router = request.app.state.router
    matched = skill_router.route(payload.utterance)
    request.app.state.active_skill = matched

    if matched is not None:
        skill_md_path = skill_router.skill_md_path(matched)
        skill_md_text = skill_md_path.read_text(encoding="utf-8")
        context_files = _load_context_files(skill_md_path)
        request.app.state.last_context_package = request.app.state.context_budget.assemble(
            skill_md_text, context_files
        )

    return {"matched_skill": matched}
