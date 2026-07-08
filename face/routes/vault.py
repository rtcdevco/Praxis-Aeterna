from __future__ import annotations

from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter()


class SaveNoteRequest(BaseModel):
    content: str
    folder: str
    title: str
    tags: list[str] | None = None


@router.post("/vault/note")
def save_note(payload: SaveNoteRequest, request: Request) -> dict:
    vault = request.app.state.vault
    extra = {"tags": payload.tags} if payload.tags else None
    path = vault.save_note(payload.content, payload.folder, payload.title, frontmatter_extra=extra)
    return {"path": str(path.relative_to(vault.vault_root))}


@router.get("/vault/search")
def search_vault(q: str, request: Request) -> dict:
    results = request.app.state.vault.search_vault(q)
    return {"results": [{"path": r.path, "title": r.title, "score": r.score} for r in results]}
