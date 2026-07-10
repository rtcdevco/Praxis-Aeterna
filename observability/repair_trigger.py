# version: 1
# changed: 2026-07-09 | Claude | initial implementation
"""Watches health score history; re-initializes failing in-process components
after 3 consecutive declining checks.

Adapted from the original spec's "automatically restarts failing service":
there's no process manager here to restart a service with — brain/memory/
voice are Python objects living in this one process. "Repair" here means
calling the same re-initialization each component already exposes for
recovering from transient failure (re-scanning the vault, re-instantiating
the voice engines), not a process-level restart.
"""

from __future__ import annotations

import time
from contextlib import closing
from dataclasses import dataclass

_SCHEMA = """
CREATE TABLE IF NOT EXISTS health_samples (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL,
    score REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS repair_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL,
    component TEXT NOT NULL,
    action TEXT NOT NULL,
    score_before REAL NOT NULL,
    score_after REAL NOT NULL
);
"""


@dataclass
class RepairResult:
    triggered: bool
    component: str | None = None
    action: str | None = None
    score_before: float | None = None
    score_after: float | None = None


class RepairTrigger:
    def __init__(self, conn, consecutive_threshold: int = 3):
        self.consecutive_threshold = consecutive_threshold
        self._conn = conn
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def record_score(self, score: float) -> None:
        with closing(self._conn.cursor()) as cur:
            cur.execute(
                "INSERT INTO health_samples (ts, score) VALUES (?, ?)", (time.time(), score)
            )
        self._conn.commit()

    def _recent_scores(self, limit: int) -> list[float]:
        with closing(self._conn.cursor()) as cur:
            cur.execute("SELECT score FROM health_samples ORDER BY ts DESC LIMIT ?", (limit,))
            return [row[0] for row in cur.fetchall()]

    def should_repair(self) -> bool:
        """True if the last `consecutive_threshold` recorded scores are strictly
        decreasing (most recent < previous < ... ), i.e. a real declining trend,
        not just "currently below some fixed number."
        """
        scores = self._recent_scores(self.consecutive_threshold)
        if len(scores) < self.consecutive_threshold:
            return False
        # scores[0] is most recent; a declining trend means each is smaller
        # than the one before it as time moves forward, i.e. scores is
        # strictly increasing when read oldest-to-newest... in our
        # newest-first list that's strictly decreasing front-to-back.
        return all(scores[i] < scores[i + 1] for i in range(len(scores) - 1))

    def attempt_repair(self, unhealthy_components: list[str], repair_actions: dict[str, callable],
                        score_before: float, score_after_fn: callable) -> RepairResult:
        """Runs the first available repair action for the first unhealthy
        component that has one registered, then re-measures health.
        `repair_actions` maps component name -> zero-arg callable that
        attempts recovery. `score_after_fn` re-computes the composite score.
        """
        for component in unhealthy_components:
            action = repair_actions.get(component)
            if action is None:
                continue

            action()
            score_after = score_after_fn()
            self._log_repair(component, action_name=action.__name__,
                              score_before=score_before, score_after=score_after)
            return RepairResult(
                triggered=True, component=component, action=action.__name__,
                score_before=score_before, score_after=score_after,
            )

        return RepairResult(triggered=False)

    def _log_repair(
        self, component: str, action_name: str, score_before: float, score_after: float
    ) -> None:
        with closing(self._conn.cursor()) as cur:
            cur.execute(
                "INSERT INTO repair_log (ts, component, action, score_before, score_after) "
                "VALUES (?, ?, ?, ?, ?)",
                (time.time(), component, action_name, score_before, score_after),
            )
        self._conn.commit()

    def repair_history(self, limit: int = 10) -> list[dict]:
        with closing(self._conn.cursor()) as cur:
            cur.execute(
                "SELECT ts, component, action, score_before, score_after "
                "FROM repair_log ORDER BY ts DESC LIMIT ?",
                (limit,),
            )
            return [
                {
                    "ts": r[0], "component": r[1], "action": r[2],
                    "score_before": r[3], "score_after": r[4],
                }
                for r in cur.fetchall()
            ]
