from core.context_budget import ContextBudget
from core.context_manager import ContextManager


def test_context_manager_active_skill_defaults_to_none():
    manager = ContextManager(ContextBudget(1000))
    assert manager.get_active_skill("s1") is None


def test_context_manager_set_and_get_active_skill():
    manager = ContextManager(ContextBudget(1000))
    manager.set_active_skill("s1", "productivity")
    assert manager.get_active_skill("s1") == "productivity"


def test_context_manager_sessions_are_isolated():
    manager = ContextManager(ContextBudget(1000))
    manager.set_active_skill("s1", "productivity")
    manager.set_active_skill("s2", "research")
    assert manager.get_active_skill("s1") == "productivity"
    assert manager.get_active_skill("s2") == "research"


def test_context_manager_last_context_package_defaults_to_none():
    manager = ContextManager(ContextBudget(1000))
    assert manager.get_last_context_package("s1") is None


def test_context_manager_assemble_stores_package_per_session():
    manager = ContextManager(ContextBudget(1000))
    package = manager.assemble("s1", "skill md text", [("file.md", "some content")])
    assert manager.get_last_context_package("s1") is package
    assert package.included_files == ["file.md"]


def test_context_manager_assemble_respects_budget():
    manager = ContextManager(ContextBudget(5))  # tiny budget
    package = manager.assemble("s1", "a" * 100, [("big.md", "b" * 100)])
    assert package.excluded_files == ["big.md"]
