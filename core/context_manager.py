"""Per-session context tracking: which skill is active, and the last assembled
ContextPackage — built on top of ContextBudget (core/context_budget.py), which
stays the single source of truth for the actual token-budget arithmetic.
"""
from __future__ import annotations

from dataclasses import dataclass

from core.context_budget import ContextBudget, ContextPackage


@dataclass
class SessionContext:
    active_skill: str | None = None
    last_context_package: ContextPackage | None = None


class ContextManager:
    def __init__(self, budget: ContextBudget):
        self.budget = budget
        self._contexts: dict[str, SessionContext] = {}

    def _get(self, session_id: str) -> SessionContext:
        return self._contexts.setdefault(session_id, SessionContext())

    def set_active_skill(self, session_id: str, skill_name: str | None) -> None:
        self._get(session_id).active_skill = skill_name

    def get_active_skill(self, session_id: str) -> str | None:
        return self._get(session_id).active_skill

    def assemble(
        self, session_id: str, skill_md_text: str, context_files: list[tuple[str, str]]
    ) -> ContextPackage:
        package = self.budget.assemble(skill_md_text, context_files)
        self._get(session_id).last_context_package = package
        return package

    def get_last_context_package(self, session_id: str) -> ContextPackage | None:
        return self._get(session_id).last_context_package
