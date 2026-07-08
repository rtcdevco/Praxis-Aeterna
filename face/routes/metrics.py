from __future__ import annotations

from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/metrics")
def get_metrics(request: Request) -> dict:
    vault = request.app.state.vault
    index = vault.scan_vault()
    graph_data = vault.get_graph_data()
    daily_notes = sum(1 for path in index.notes if path.startswith("01-daily/"))

    context_budget = request.app.state.context_budget
    package = request.app.state.last_context_package

    return {
        "vault_nodes": index.node_count,
        "graph_links": len(graph_data["edges"]),
        "daily_notes": daily_notes,
        "context_usage": {
            "used_tokens": package.total_tokens if package else 0,
            "budget_tokens": context_budget.max_tokens,
            "ratio": package.usage_ratio if package else 0.0,
        },
        "active_skill": request.app.state.active_skill,
    }
