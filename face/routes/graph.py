from __future__ import annotations

from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/graph")
def get_graph(request: Request) -> dict:
    return request.app.state.vault.get_graph_data()
