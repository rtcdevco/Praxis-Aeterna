"""ContextBudget — enforces the Brain's conservative per-invocation token budget.

`SKILL.md` is always included (mandatory). Declared context files are added in
priority order, running a cumulative token count; the first file that would
push the total over budget is excluded, and everything after it is excluded
too ("stop when full" — simple and predictable rather than trying to
cleverly repack around a gap).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


class TokenCounter(Protocol):
    def count_tokens(self, text: str) -> int: ...


class HeuristicTokenCounter:
    """A documented ~4-chars-per-token estimate for English prose.

    This is NOT Claude's real tokenizer. It exists because this phase makes no
    live Claude API calls to count against, and `tiktoken` would be the wrong
    tokenizer for Claude content (it under-counts relative to Claude's actual
    tokenizer). Swap point for a future phase that makes live model calls:
    implement a `TokenCounter` backed by `client.messages.count_tokens(...)`
    (the real Anthropic endpoint) — callers only depend on this Protocol, so
    no other code needs to change.
    """

    def count_tokens(self, text: str) -> int:
        return len(text) // 4 + 1


@dataclass
class ContextPackage:
    budget: int
    total_tokens: int
    included_files: list[str] = field(default_factory=list)
    excluded_files: list[str] = field(default_factory=list)

    @property
    def usage_ratio(self) -> float:
        return self.total_tokens / self.budget if self.budget else 0.0


class ContextBudget:
    def __init__(self, max_tokens: int, counter: TokenCounter | None = None):
        self.max_tokens = max_tokens
        self.counter = counter or HeuristicTokenCounter()

    def assemble(self, skill_md_text: str, context_files: list[tuple[str, str]]) -> ContextPackage:
        """`context_files` is a list of (name, content) pairs in priority order."""
        total = self.counter.count_tokens(skill_md_text)
        included: list[str] = []
        excluded: list[str] = []
        full = False

        for name, content in context_files:
            if full:
                excluded.append(name)
                continue
            tokens = self.counter.count_tokens(content)
            if total + tokens > self.max_tokens:
                excluded.append(name)
                full = True
                continue
            total += tokens
            included.append(name)

        return ContextPackage(
            budget=self.max_tokens,
            total_tokens=total,
            included_files=included,
            excluded_files=excluded,
        )
