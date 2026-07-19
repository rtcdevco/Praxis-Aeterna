"""Session lifecycle tracking.

In-memory only, one process — sessions reset on restart. That's intentional:
durable state already has a home (the vault for content, the observability DB
for metrics/history); a Session here is just "how long has this conversation
been going," not a place to persist anything.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

DEFAULT_SESSION_ID = "default"


@dataclass
class Session:
    id: str
    created_at: float = field(default_factory=time.time)
    last_active_at: float = field(default_factory=time.time)

    def touch(self) -> None:
        self.last_active_at = time.time()

    @property
    def age_seconds(self) -> float:
        return time.time() - self.created_at

    @property
    def idle_seconds(self) -> float:
        return time.time() - self.last_active_at


class SessionManager:
    def __init__(self):
        self._sessions: dict[str, Session] = {}

    def get_or_create(self, session_id: str = DEFAULT_SESSION_ID) -> Session:
        session = self._sessions.get(session_id)
        if session is None:
            session = Session(id=session_id)
            self._sessions[session_id] = session
        else:
            session.touch()
        return session

    def end(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)

    @property
    def active_count(self) -> int:
        return len(self._sessions)
