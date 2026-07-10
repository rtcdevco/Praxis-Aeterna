# Build Plan — Observability (Step 03)

Reference input: a direct implementation spec for "System Observability &
Metrics Infrastructure" (six modules: metrics collector, drift detector,
version audit trail, health check aggregator, self-repair trigger, dashboard
integration). No Linear tickets were created for this pass.

## Adaptations from the literal spec

This app is a single FastAPI process, not five independently-running
services, so several pieces were grounded in that reality rather than
implemented literally:

- **"Poll all existing services"** → each health check calls the real
  in-process object directly (`SkillRouter`, `VaultConnector`, `VoiceOS`).
  There's no network to poll over.
- **"Automatically restarts failing service"** → there's no process manager
  to restart a service with. "Repair" re-initializes the specific in-process
  component using its own existing recovery path (`vault.scan_vault
  (force_rescan=True)`, a fresh `VoiceOS()`, regenerating the skill
  manifest), not an OS-level restart.
- **`handoff`** isn't a runtime component — its "health" is a static
  file-presence check (deploy assets exist on disk), not a live poll.
- **Dashboard integration** was explicitly declined (UI edit denied) — kept
  API-only. All data is available via the endpoints below; a future pass can
  add the UI without touching the observability modules themselves.
- **`/api/metrics` already existed** (dashboard-shaped JSON from Phase 1) —
  the new Prometheus-format endpoint lives at `/api/observability/metrics`
  instead of colliding with it.

## Tech stack

All stdlib, no new runtime dependencies beyond what the app already ships:

| Concern | Choice | Why |
|---|---|---|
| Storage | `sqlite3` (stdlib) | One file (`observability_data.db`), same pattern as everything else in this repo being file-based (vault, manifest). |
| Memory sampling | `resource.getrusage` (stdlib) | No `psutil` needed for a single RSS number. |
| Statistics | `statistics.mean`/`pstdev` (stdlib) | Real numbers computed from actual recorded requests, not hardcoded constants. |
| Metrics format | Hand-built Prometheus text exposition format | No `prometheus_client` dependency needed for six gauge/counter lines. |

## File structure

```
observability/
├── __init__.py
├── metrics_collector.py   # request/error/memory metrics, SQLite-backed, Prometheus text export
├── drift_detector.py      # 2-sigma latency/error-rate anomaly detection, incident log
├── version_audit.py       # file-hash + version-header change tracking
├── health_aggregator.py   # composite 0.0-1.0 score across the five pillars
└── repair_trigger.py      # declining-trend detection + in-process component re-init

face/routes/observability.py   # /observability/metrics, /observability/incidents, /health/score, /audit/log
face/main.py                   # wires app.state.{metrics_collector,drift_detector,version_audit,
                                #   health_aggregator,repair_trigger}; HTTP middleware records every request

tests/test_observability.py    # unit tests, one file per module's behavior
tests/test_api.py              # extended: endpoint tests + a full repair-trigger integration scenario
```

## Integration points

- **The FastAPI middleware in `face/main.py` (`record_metrics`) is the single
  place every request's latency/status gets recorded** — no route handler
  calls `MetricsCollector` directly for its own traffic; this is why "voice
  engine throughput" doesn't need a separate tracking mechanism, it's derived
  from `path LIKE '/api/voice/%'` against the same table.
- **`/api/health/score` triggers repair as a side effect of being polled**,
  rather than a background asyncio loop. This avoids lifespan/background-task
  complexity and test flakiness (57+ tests each spinning up a fresh app
  instance) — the existing dashboard's 5-second poll interval already
  provides a natural cadence once/if a UI polls this endpoint.
- **`HealthAggregator` holds direct references** to `router`/`vault`/
  `voice_os`; when repair re-instantiates one (e.g. a fresh `VoiceOS()`), the
  repair action updates `health_aggregator.<attr>` too, or the aggregator
  would keep checking the old, replaced object. Found and fixed during
  testing — see "Bugs found" below.
- **Version audit is opt-in per file** via a `# version: N` / `# changed:
  ...` header; `record_change()` raises if the header is missing rather than
  silently skipping, so a file can't be "audited" without deliberately
  adopting the convention.

## Sequencing

Built in this order (matches natural dependency, no separate ticket graph
since there were no tickets this pass):

1. `metrics_collector.py` (nothing depends on it existing first, but
   everything else reads from it)
2. `drift_detector.py`, `version_audit.py` (independent, both read the same
   SQLite connection `metrics_collector` opened)
3. `health_aggregator.py` (needs real `router`/`vault`/`voice_os` instances)
4. `repair_trigger.py` (needs a health score to watch)
5. `face/routes/observability.py` + `face/main.py` wiring (ties everything
   into the running app)
6. Tests throughout each step, not deferred to the end

## Bugs found and fixed during implementation

- **`HealthAggregator.report()` crashed instead of degrading gracefully**
  when `voice_os.status()` raised. `check_voice()` (used for the composite
  score) already handled this correctly; `report()` called `voice_os.status()`
  a second, unprotected time for the `voice_engines_available` field. Fixed
  to catch and report `{"stt": None, "tts": None}` instead of crashing the
  whole `/api/health/score` request. Caught by
  `test_health_score_repairs_after_declining_trend` in `test_api.py`.
- **Drift detector missed the most obvious anomaly case**: when recent
  history has exactly zero variance (e.g. 10 identical latencies) and the
  latest sample differs, the original code treated "stddev == 0" as "can't
  compare" and returned no incident — but zero-variance-then-a-huge-outlier
  is the single clearest anomaly signal possible. Fixed to flag any deviation
  from a zero-variance history as an incident (infinite z-score), rather than
  suppressing it. Caught by `test_drift_detector_flags_latency_spike`.
- **e2e test flakiness (~20% failure rate) exposed by the new middleware's
  added per-request latency**: `test_dashboard_renders_seeded_metrics` only
  waited for `#metric-vault-nodes` to update before asserting on
  `#skills-list`, but `refreshSkills()` and `refreshMetrics()` run
  concurrently in the dashboard's `refreshAll()` — a pre-existing race that
  became likelier once SQLite writes added latency to every request. Fixed
  by adding an explicit wait for `#skills-list` too; confirmed stable across
  6 consecutive runs after the fix (was failing ~1-in-5 before).

## Not covered here

- Dashboard UI for metrics graphs, drift alerts, health timeline, or the
  audit log — declined this pass; data is fully available via the API.
- Linear ticket creation for this work — declined this pass; this doc is the
  paper trail instead.
