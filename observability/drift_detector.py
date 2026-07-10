# version: 1
# changed: 2026-07-09 | Claude | initial implementation
"""Statistical anomaly detection over request metrics: latency spikes and error
clustering, flagged when a sample is more than N standard deviations from the
rolling mean of recent samples. Real statistics (stdlib `statistics`), not a
hardcoded threshold pretending to be adaptive.
"""

from __future__ import annotations

import statistics
import time
import uuid
from contextlib import closing
from dataclasses import dataclass

from observability.metrics_collector import MetricsCollector

_SCHEMA = """
CREATE TABLE IF NOT EXISTS incidents (
    id TEXT PRIMARY KEY,
    ts REAL NOT NULL,
    component TEXT NOT NULL,
    kind TEXT NOT NULL,
    detail TEXT NOT NULL,
    recovery_action TEXT NOT NULL
);
"""


@dataclass
class Incident:
    id: str
    ts: float
    component: str
    kind: str
    detail: str
    recovery_action: str


class DriftDetector:
    def __init__(self, collector: MetricsCollector, sigma_threshold: float = 2.0):
        self.collector = collector
        self.sigma_threshold = sigma_threshold
        self._conn = collector._conn  # share the same SQLite connection/db file
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def check_latency_drift(self, component: str = "api", sample_size: int = 50) -> Incident | None:
        """Compare the most recent request's latency to the mean/stddev of the
        `sample_size` requests before it. Needs at least 5 prior samples to
        compute a meaningful stddev; returns None (no incident) otherwise —
        not enough history to call anything an anomaly yet.
        """
        latencies = self.collector.recent_latencies(limit=sample_size + 1)
        if len(latencies) < 6:
            return None

        latest, history = latencies[0], latencies[1:]
        mean = statistics.mean(history)
        stddev = statistics.pstdev(history)

        if stddev == 0:
            # Zero-variance history: any deviation at all is anomalous (there's
            # no "normal spread" to measure against), so this isn't a "can't
            # tell" case — it's the most obvious possible signal.
            if latest == mean:
                return None
            z_score = float("inf")
        else:
            z_score = abs(latest - mean) / stddev
            if z_score < self.sigma_threshold:
                return None

        return self._log_incident(
            component=component,
            kind="latency_spike",
            detail=(
                f"latency={latest:.1f}ms is {z_score:.2f} sigma from the "
                f"{len(history)}-sample mean ({mean:.1f}ms, stddev={stddev:.1f}ms)"
            ),
            recovery_action="logged for review; no automatic action for latency alone",
        )

    def check_error_clustering(
        self, window: int = 20, baseline_window: int = 200
    ) -> Incident | None:
        """Compare the error rate in the most recent `window` requests against
        the error rate over `baseline_window` requests. Flags when the recent
        rate is more than sigma_threshold standard deviations above baseline,
        modeling errors as a binomial rate (real stats, not a magic constant).
        """
        with closing(self._conn.cursor()) as cur:
            cur.execute(
                "SELECT status_code FROM request_metrics ORDER BY ts DESC LIMIT ?",
                (baseline_window,),
            )
            rows = [row[0] for row in cur.fetchall()]

        if len(rows) < window + 5:
            return None

        recent = rows[:window]
        baseline = rows
        baseline_rate = sum(1 for c in baseline if c >= 400) / len(baseline)
        recent_rate = sum(1 for c in recent if c >= 400) / len(recent)

        # Standard error of a binomial proportion at the baseline rate — the
        # real basis for "how many sigma above baseline is this," not a
        # fixed percentage-point threshold.
        stderr = (baseline_rate * (1 - baseline_rate) / window) ** 0.5
        if stderr == 0:
            return None

        z_score = (recent_rate - baseline_rate) / stderr
        if z_score < self.sigma_threshold:
            return None

        return self._log_incident(
            component="api",
            kind="error_clustering",
            detail=(
                f"recent error rate {recent_rate:.2%} over last {window} requests is "
                f"{z_score:.2f} sigma above baseline {baseline_rate:.2%} "
                f"(n={len(baseline)})"
            ),
            recovery_action="logged for review; no automatic action for errors alone",
        )

    def _log_incident(
        self, component: str, kind: str, detail: str, recovery_action: str
    ) -> Incident:
        incident = Incident(
            id=str(uuid.uuid4()),
            ts=time.time(),
            component=component,
            kind=kind,
            detail=detail,
            recovery_action=recovery_action,
        )
        with closing(self._conn.cursor()) as cur:
            cur.execute(
                "INSERT INTO incidents (id, ts, component, kind, detail, recovery_action) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (incident.id, incident.ts, incident.component, incident.kind,
                 incident.detail, incident.recovery_action),
            )
        self._conn.commit()
        return incident

    def recent_incidents(self, limit: int = 10) -> list[dict]:
        with closing(self._conn.cursor()) as cur:
            cur.execute(
                "SELECT id, ts, component, kind, detail, recovery_action "
                "FROM incidents ORDER BY ts DESC LIMIT ?",
                (limit,),
            )
            return [
                {
                    "id": r[0], "ts": r[1], "component": r[2],
                    "kind": r[3], "detail": r[4], "recovery_action": r[5],
                }
                for r in cur.fetchall()
            ]
