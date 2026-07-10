# version: 1
# changed: 2026-07-09 | Claude | initial implementation
"""Request/error/memory metrics, backed by SQLite, exposed in Prometheus text format.

Deliberately separate from the existing `/api/metrics` route (face/routes/metrics.py),
which serves dashboard-shaped JSON about vault/skill state — this module is
generic request-level telemetry (latency, status codes, process memory), collected
via middleware, not tied to any one route's business logic.
"""

from __future__ import annotations

import resource
import sqlite3
import time
from contextlib import closing
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS request_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL,
    path TEXT NOT NULL,
    method TEXT NOT NULL,
    duration_ms REAL NOT NULL,
    status_code INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_request_metrics_ts ON request_metrics(ts);
CREATE INDEX IF NOT EXISTS idx_request_metrics_path ON request_metrics(path);

CREATE TABLE IF NOT EXISTS memory_samples (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL,
    rss_kb INTEGER NOT NULL
);
"""


class MetricsCollector:
    """Owns one SQLite connection; safe for single-process use (this app is one process)."""

    def __init__(self, db_path: str | Path, retention_days: int = 30):
        self.db_path = str(db_path)
        self.retention_days = retention_days
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def record_request(self, path: str, method: str, duration_ms: float, status_code: int) -> None:
        with closing(self._conn.cursor()) as cur:
            cur.execute(
                "INSERT INTO request_metrics (ts, path, method, duration_ms, status_code) "
                "VALUES (?, ?, ?, ?, ?)",
                (time.time(), path, method, duration_ms, status_code),
            )
        self._conn.commit()
        self._prune()

    def sample_memory(self) -> int:
        """Record and return current process RSS in KB (stdlib `resource`, no new dep)."""
        rss_kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        with closing(self._conn.cursor()) as cur:
            cur.execute(
                "INSERT INTO memory_samples (ts, rss_kb) VALUES (?, ?)", (time.time(), rss_kb)
            )
        self._conn.commit()
        return rss_kb

    def _prune(self) -> None:
        cutoff = time.time() - self.retention_days * 86400
        with closing(self._conn.cursor()) as cur:
            cur.execute("DELETE FROM request_metrics WHERE ts < ?", (cutoff,))
            cur.execute("DELETE FROM memory_samples WHERE ts < ?", (cutoff,))
        self._conn.commit()

    def recent_latencies(self, path_prefix: str | None = None, limit: int = 200) -> list[float]:
        query = "SELECT duration_ms FROM request_metrics"
        params: tuple = ()
        if path_prefix:
            query += " WHERE path LIKE ?"
            params = (f"{path_prefix}%",)
        query += " ORDER BY ts DESC LIMIT ?"
        params = params + (limit,)
        with closing(self._conn.cursor()) as cur:
            cur.execute(query, params)
            return [row[0] for row in cur.fetchall()]

    def summary(self) -> dict:
        with closing(self._conn.cursor()) as cur:
            cur.execute("SELECT COUNT(*), AVG(duration_ms) FROM request_metrics")
            total_requests, avg_latency = cur.fetchone()
            cur.execute("SELECT COUNT(*) FROM request_metrics WHERE status_code >= 400")
            (error_count,) = cur.fetchone()
            cur.execute(
                "SELECT COUNT(*) FROM request_metrics WHERE path LIKE '/api/voice/%'"
            )
            (voice_requests,) = cur.fetchone()
            cur.execute("SELECT rss_kb FROM memory_samples ORDER BY ts DESC LIMIT 1")
            row = cur.fetchone()
            latest_rss_kb = row[0] if row else 0

        total_requests = total_requests or 0
        error_rate = (error_count / total_requests) if total_requests else 0.0
        return {
            "total_requests": total_requests,
            "avg_latency_ms": avg_latency or 0.0,
            "error_count": error_count or 0,
            "error_rate": error_rate,
            "voice_requests": voice_requests or 0,
            "memory_rss_kb": latest_rss_kb,
        }

    def prometheus_text(self) -> str:
        s = self.summary()
        lines = [
            "# HELP fable5_requests_total Total HTTP requests observed.",
            "# TYPE fable5_requests_total counter",
            f"fable5_requests_total {s['total_requests']}",
            "# HELP fable5_request_duration_ms_avg Average request latency in milliseconds.",
            "# TYPE fable5_request_duration_ms_avg gauge",
            f"fable5_request_duration_ms_avg {s['avg_latency_ms']}",
            "# HELP fable5_request_errors_total Requests with status code >= 400.",
            "# TYPE fable5_request_errors_total counter",
            f"fable5_request_errors_total {s['error_count']}",
            "# HELP fable5_request_error_rate Error rate over all recorded requests.",
            "# TYPE fable5_request_error_rate gauge",
            f"fable5_request_error_rate {s['error_rate']}",
            "# HELP fable5_voice_requests_total Requests to /api/voice/* routes.",
            "# TYPE fable5_voice_requests_total counter",
            f"fable5_voice_requests_total {s['voice_requests']}",
            "# HELP fable5_memory_rss_kb Process resident set size in KB (latest sample).",
            "# TYPE fable5_memory_rss_kb gauge",
            f"fable5_memory_rss_kb {s['memory_rss_kb']}",
        ]
        return "\n".join(lines) + "\n"

    def close(self) -> None:
        self._conn.close()
