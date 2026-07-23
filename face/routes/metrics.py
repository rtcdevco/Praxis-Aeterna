from __future__ import annotations

from fastapi import APIRouter, Request

from core.session import DEFAULT_SESSION_ID

router = APIRouter()


@router.get("/metrics")
def get_metrics(request: Request, session_id: str = DEFAULT_SESSION_ID) -> dict:
    vault = request.app.state.vault
    index = vault.scan_vault()
    graph_data = vault.get_graph_data()
    daily_notes = sum(1 for path in index.notes if path.startswith("01-daily/"))

    context_manager = request.app.state.context_manager
    package = context_manager.get_last_context_package(session_id)

    return {
        "vault_nodes": index.node_count,
        "graph_links": len(graph_data["edges"]),
        "daily_notes": daily_notes,
        "context_usage": {
            "used_tokens": package.total_tokens if package else 0,
            "budget_tokens": context_manager.budget.max_tokens,
            "ratio": package.usage_ratio if package else 0.0,
        },
        "active_skill": context_manager.get_active_skill(session_id),
    }
