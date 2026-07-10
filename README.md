# Fable 5 OS

A local, voice-driven AI command center — modular skills, an Obsidian-compatible
memory vault, local voice, and a unified V.A.U.L.T. dashboard, all in one repo.
Built with the [Fable 5 methodology](./CLAUDE.md): Sonnet 5 brainstorms it,
Linear structures it, Fable 5 plans it, Opus-tier agents build it.

## Five pillars

| Pillar | Component | Status |
|---|---|---|
| The Brain | Skill router (`core/`) | ✅ Phase 1 |
| The Memory | Obsidian-compatible vault (`vault_connector/`) | ✅ Phase 1 |
| The Face | FastAPI + V.A.U.L.T. dashboard (`face/`) | ✅ Phase 1 |
| The Voice | Local STT + TTS (`voice/`) | ✅ Phase 2 (engine + wiring; real STT/TTS deps unverified) |
| The Handoff | Deploy + client-reskin scripts | ✅ Phase 3 (`local`/Dockerfile/systemd written; only `local` verified) |

Voice and Handoff are now built, but two things inside them still need a real
environment to verify, not this sandbox:
- **Voice**: `voice/engines.py` and its API wiring are fully unit-tested with
  mocked STT/TTS deps, but installing the real `faster-whisper`/`kokoro-onnx`
  packages and downloading model files needs real network access and hardware
  — see `requirements-voice.txt` and Linear ticket PRA-6.
- **Handoff**: `./deploy.sh local` is verified end-to-end (boots the real app,
  serves the dashboard and voice endpoints). The `docker` and `systemd` modes
  are written and match the actual current entrypoint (`face.main:app`), but
  need a host with Docker / a real init system + sudo to verify — this
  sandbox container has neither. See Linear tickets PRA-7/8/11.

## What's here

- **`core/`** — skill discovery + manifest generation, a two-phase
  (regex-then-keyword) intent router, and a token-budget-aware context
  assembler.
- **`vault_connector/`** — reads/writes the `vault/` directory (plain Markdown
  + `[[wikilinks]]`, no database): scanning, saving notes, scored search, a
  wikilink knowledge graph, and daily-note templating.
- **`face/`** — a FastAPI backend and a static (no-build-step) dashboard that
  polls it, showing live metrics, the skill list, voice status, and a
  D3 force-directed graph of the vault.
- **`skills/`** — starter skills (`productivity`, `research`), each a
  self-contained folder with a `SKILL.md` definition.
- **`vault/`** — the Obsidian-compatible data directory (`00-inbox` through
  `06-archive`); most subfolders are gitignored at the content level so your
  own notes don't get committed, only the structure does.
- **`voice/`** — `STTEngine` (faster-whisper) and `TTSEngine` (Kokoro ONNX),
  both optional at import time; a `VoiceOS` facade the API layer talks to.
- **`deploy/`** — the systemd unit (`fable5.service`) and `scripts/reskin.sh`
  for cloning + rebranding the whole repo for a client.
- **`observability/`** — metrics, drift detection, health scoring, self-repair,
  and a version audit log. See "Observability" below.
- **`docs/fable5/`** — the methodology's step-by-step templates (unrelated to
  the product code above; describes *how* work happens in this repo).

## Getting started

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # add ANTHROPIC_API_KEY (not yet consumed by any code path, but required by deploy configs)

uvicorn face.main:app --reload
```

Then open http://127.0.0.1:8000 for the V.A.U.L.T. dashboard.

Voice deps (`faster-whisper`, `kokoro-onnx`, `soundfile`) are optional and not
installed above — install with `pip install -r requirements-voice.txt` if you
want real STT/TTS instead of the graceful "unavailable" fallback; model files
(e.g. `kokoro-v0_19.onnx`, `voices.bin`) go in `models/`.

## Deploy modes

```bash
./deploy.sh local     # dev/personal — verified in this repo's CI sandbox
./deploy.sh docker    # reproducible — needs Docker on the host
./deploy.sh systemd   # production Linux, boot autostart — needs sudo + systemd
```

## Client reskin

```bash
./deploy/scripts/reskin.sh acme-corp   # creates ../acme-corp-os, rebranded, git-initialized
```

## Observability

`observability/` adds request-level metrics, statistical drift detection, a
composite health score, self-repair, and a file-change audit log — API-only
for now, no dashboard UI (kept out of scope for this pass; see below).

This app is one process, not five independently-running services, so a few
things from a typical multi-service observability stack were adapted rather
than followed literally:

- **Metrics** (`GET /api/observability/metrics`, Prometheus text format):
  request counts, average latency, error rate, `/api/voice/*` request count,
  and process RSS memory (via stdlib `resource`, no new dependency). Stored in
  SQLite (`observability_data.db`, gitignored, path configurable via
  `OBSERVABILITY_DB_PATH`), pruned to `METRICS_RETENTION_DAYS` (default 30).
- **Drift detection** (`GET /api/observability/incidents`): flags a latency
  sample or a burst of errors as anomalous when it's more than
  `DRIFT_SIGMA_THRESHOLD` (default 2.0) standard deviations from recent
  history — real statistics (`statistics.mean`/`pstdev`), not a fixed
  percentage threshold.
- **Health score** (`GET /api/health/score`, 0.0–1.0): checks brain (skill
  router loaded), memory (vault scan succeeds), face (trivially healthy —
  it's the process answering the request), voice (status call succeeds; STT/
  TTS being unavailable is expected default behavior, not unhealthy), and
  handoff (deploy assets present on disk — a static check, since handoff
  isn't a live runtime component).
- **Self-repair**: if the health score has strictly declined for
  `REPAIR_CONSECUTIVE_THRESHOLD` (default 3) consecutive checks, the next
  `/api/health/score` call re-initializes the first unhealthy component it
  has a real recovery action for — re-scanning the vault, re-instantiating
  the voice engines, or regenerating the skill manifest — and reports
  before/after scores. There's no separate process to "restart"; repair means
  calling the same recovery path each component already exposes.
- **Version audit log** (`GET /api/audit/log`): files opt in via a
  `# version: N` / `# changed: ...` header (see any file in `observability/`
  for the convention); `record_change()`/`check_version_bumped()` hash the
  file and flag a content change without a matching version bump. Scoped to
  `observability/` in this PR — existing brain/memory/face/voice files don't
  carry the header and weren't retrofitted, since editing them was out of
  scope.

Not done: dashboard UI for any of this (metrics graphs, drift alerts, health
timeline, audit log view) — left out of this pass to avoid dashboard
structural changes; the data is fully available via the API above if a UI
gets added later.

## Tests

```bash
pytest
```

Unit tests cover the skill router, context budget, vault connector, wikilink
graph, voice engines (STT/TTS, mocked so no real audio deps are needed),
env-based config, and the observability modules (metrics, drift detection,
version audit, health aggregation, repair triggering) in isolation (pure
Python, no external services). `test_api.py` exercises every `/api/*` route
via FastAPI's `TestClient`, including the voice endpoints' graceful-unavailable
behavior and a full health-score-triggers-repair scenario. `tests/e2e/` drives
a real headless-Chromium session against a seeded vault and asserts the
dashboard renders the actual seeded numbers, including live (not stubbed)
voice status — proof the full stack is wired correctly, not just unit-correct
in isolation.
