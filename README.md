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
- **Voice**: every module (`stt_engine.py`, `tts_engine.py`, `audio_capture.py`,
  `audio_playback.py`, `intent_router.py`, `wake_word.py`, `voice_os.py`) and
  its API wiring are fully unit-tested with mocked STT/TTS/`sounddevice` deps,
  but installing the real packages, downloading model files, and testing
  against a real mic/speakers needs real network access and hardware — see
  `requirements-voice.txt`.
- **Handoff**: `./deploy.sh local` is verified end-to-end (boots the real app,
  serves the dashboard and voice endpoints). The `docker` and `systemd` modes
  are written and match the actual current entrypoint (`face.main:app`), but
  need a host with Docker / a real init system + sudo to verify — this
  sandbox container has neither.

## What's here

- **`core/`** — skill discovery + manifest generation, a two-phase
  (regex-then-keyword) intent router, a token-budget-aware context assembler,
  and per-session tracking (`session.py` for lifecycle, `context_manager.py`
  for active-skill/context-package state) — currently backing one implicit
  "default" session, but the primitives support more.
- **`vault_connector/`** — reads/writes the `vault/` directory (plain Markdown
  + `[[wikilinks]]`, no database): scanning, saving notes, scored search, a
  wikilink knowledge graph, and daily-note templating.
- **`face/`** — a FastAPI backend and a static (no-build-step) dashboard that
  polls it, showing live metrics, the skill list, voice status, and a
  D3 force-directed graph of the vault.
- **`skills/`** — `productivity`, `research`, `content`, `sales`, `finance`,
  `ops`, each a self-contained folder with a `SKILL.md` definition following
  the same Identity/Context Files/Capabilities/Output Format/Rules/Vault Save
  template.
- **`vault/`** — the Obsidian-compatible data directory (`00-inbox` through
  `06-archive`); most subfolders are gitignored at the content level so your
  own notes don't get committed, only the structure does.
- **`voice/`** — one module per pipeline stage: `stt_engine.py`
  (faster-whisper), `tts_engine.py` (Kokoro ONNX), `audio_capture.py` (mic +
  RMS-energy VAD), `audio_playback.py` (speaker output), `intent_router.py`
  (routes a transcript through the same `SkillRouter` a typed utterance uses,
  plus wake-phrase stripping), `wake_word.py` (wake-phrase detection by
  reusing `STTEngine` rather than a separate proprietary keyword-spotting
  dependency), and `voice_os.py` (the `VoiceOS` facade the API layer talks
  to). All hardware-touching pieces (`sounddevice` for capture/playback,
  `faster-whisper`/`kokoro-onnx` for STT/TTS) are optional at import time —
  see "Voice" below for what's actually verified vs. not.
- **`deploy/`** — the systemd unit (`fable5.service`) and `scripts/reskin.sh`
  for cloning + rebranding the whole repo for a client.
- **`observability/`** — metrics, drift detection, health scoring, self-repair,
  and a version audit log. See "Observability" below.
- **`config/voice_patterns.json`** — the wake phrase and per-skill voice
  command examples, read via `voice.intent_router.load_voice_patterns()`.
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

Voice deps (`faster-whisper`, `kokoro-onnx`, `soundfile`, `sounddevice`) are
optional and not installed above — install with
`pip install -r requirements-voice.txt` if you want real STT/TTS/mic/speaker
support instead of the graceful "unavailable" fallback; model files (e.g.
`kokoro-v0_19.onnx`, `voices.bin`) go in `models/`.

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

Unit tests cover the skill router, context budget, session/context-manager,
vault connector, wikilink graph, the full voice pipeline (STT/TTS/audio
capture/audio playback/intent routing/wake word, all mocked so no real audio
deps or hardware are needed), env-based config, and the observability modules
(metrics, drift detection, version audit, health aggregation, repair
triggering) in isolation (pure Python, no external services). `test_api.py`
exercises every `/api/*` route via FastAPI's `TestClient`, including the voice
endpoints' graceful-unavailable behavior and a full health-score-triggers-repair
scenario. `tests/e2e/` drives a real headless-Chromium session against a
seeded vault and asserts the dashboard renders the actual seeded numbers,
including live (not stubbed)
voice status — proof the full stack is wired correctly, not just unit-correct
in isolation.
