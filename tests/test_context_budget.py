from core.context_budget import ContextBudget, HeuristicTokenCounter


class FixedLengthCounter:
    """A counter with an exact, known token-per-char rate for deterministic tests."""

    def count_tokens(self, text: str) -> int:
        return len(text)


def test_heuristic_counter_is_monotonic_and_approximate():
    counter = HeuristicTokenCounter()
    short = counter.count_tokens("hi")
    long = counter.count_tokens("hi " * 100)
    assert long > short
    assert counter.count_tokens("") == 1  # documented approximation, not exact


def test_all_files_included_when_under_budget():
    budget = ContextBudget(max_tokens=100, counter=FixedLengthCounter())
    package = budget.assemble("skill" * 2, [("a.md", "x" * 10), ("b.md", "y" * 10)])

    assert package.included_files == ["a.md", "b.md"]
    assert package.excluded_files == []
    assert package.total_tokens == 10 + 10 + 10  # "skillskill" is 10 chars


def test_stops_and_excludes_everything_once_full():
    budget = ContextBudget(max_tokens=25, counter=FixedLengthCounter())
    # skill_md is mandatory: 10 tokens. Budget for context files: 15.
    package = budget.assemble(
        "x" * 10,
        [("a.md", "y" * 10), ("b.md", "z" * 10), ("c.md", "w" * 5)],
    )

    # a.md fits (10+10=20 <= 25). b.md would push to 30 > 25 -> excluded, and
    # everything after b.md (c.md) is excluded too, even though c.md alone
    # would have fit.
    assert package.included_files == ["a.md"]
    assert package.excluded_files == ["b.md", "c.md"]
    assert package.total_tokens == 20


def test_mandatory_skill_md_always_counted_even_alone_over_budget():
    budget = ContextBudget(max_tokens=5, counter=FixedLengthCounter())
    package = budget.assemble("x" * 10, [("a.md", "y")])

    assert package.total_tokens == 10
    assert package.included_files == []
    assert package.excluded_files == ["a.md"]


def test_usage_ratio():
    budget = ContextBudget(max_tokens=20, counter=FixedLengthCounter())
    package = budget.assemble("x" * 10, [])
    assert package.usage_ratio == 0.5
