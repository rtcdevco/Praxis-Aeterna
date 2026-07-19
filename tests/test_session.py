import time

from core.session import DEFAULT_SESSION_ID, Session, SessionManager


def test_session_touch_updates_last_active():
    session = Session(id="s1")
    original = session.last_active_at
    time.sleep(0.01)
    session.touch()
    assert session.last_active_at > original


def test_session_age_and_idle_seconds_are_nonnegative():
    session = Session(id="s1")
    assert session.age_seconds >= 0
    assert session.idle_seconds >= 0


def test_session_manager_creates_session_on_first_access():
    manager = SessionManager()
    assert manager.active_count == 0
    session = manager.get_or_create("s1")
    assert session.id == "s1"
    assert manager.active_count == 1


def test_session_manager_returns_same_session_on_repeat_access():
    manager = SessionManager()
    first = manager.get_or_create("s1")
    second = manager.get_or_create("s1")
    assert first is second
    assert manager.active_count == 1


def test_session_manager_touches_on_repeat_access():
    manager = SessionManager()
    session = manager.get_or_create("s1")
    original = session.last_active_at
    time.sleep(0.01)
    manager.get_or_create("s1")
    assert session.last_active_at > original


def test_session_manager_default_session_id():
    manager = SessionManager()
    session = manager.get_or_create()
    assert session.id == DEFAULT_SESSION_ID


def test_session_manager_end_removes_session():
    manager = SessionManager()
    manager.get_or_create("s1")
    manager.end("s1")
    assert manager.active_count == 0


def test_session_manager_end_missing_session_is_a_noop():
    manager = SessionManager()
    manager.end("does-not-exist")  # must not raise
    assert manager.active_count == 0
