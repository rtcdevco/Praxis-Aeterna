# Build Plan — Fable 5 OS Phase 2/3: Voice & Handoff (Step 03)

Reference input: the 9-ticket Linear project
[Fable 5 OS — Voice & Handoff](https://linear.app/praxis-aeterna/project/fable-5-os-voice-and-handoff-bc164f6591e5)
(PRA-5 through PRA-13). This doc is the Step 03 output for that project.

## Tech stack

Kept identical to the original Fable 5 OS design intent, adjusted only where
the merged Phase 1 code diverged from it (`face.main:app`, not `api.server:app`):

| Concern | Choice | Why |
|---|---|---|
| STT | faster-whisper, imported lazily | 100% local, no API calls; optional so base install stays light. |
| TTS | Kokoro ONNX, imported lazily | Same optional-at-import pattern as STT. |
| Voice deps distribution | `requirements-voice.txt`, not `pyproject.toml` extras | `pyproject.toml` has no `[project]` table in this repo (it's requirements.txt-based, not a packaged distribution) — a separate optional requirements file matches the existing convention instead of inventing packaging metadata that isn't otherwise used. |
| Secrets | `.env` + `python-dotenv`, read once in `config/settings.py` | Both the systemd unit (`EnvironmentFile=`) and Docker (`--env-file`) deploy modes depend on `.env` existing; `python-dotenv` makes local dev match that without exporting vars by hand. |
| Deploy | `Dockerfile` + `deploy.sh` (local/docker/systemd) + `deploy/fable5.service` | Matches the original design's three modes exactly, updated for the current entrypoint. |
| Reskin | `deploy/scripts/reskin.sh` | Same clone-and-rebrand approach, updated file list for the current repo layout. |

## File structure

```
voice/
├── __init__.py
└── engines.py            # STTEngine, TTSEngine, VoiceOS — PRA-5

face/routes/voice.py       # GET /voice/status, POST /voice/transcribe, /voice/synthesize — PRA-10
face/main.py               # app.state.voice = VoiceOS()

config/settings.py         # ANTHROPIC_API_KEY, FABLE5_MODEL, require_anthropic_api_key() — PRA-9
.env.example                # PRA-9

Dockerfile                  # PRA-7
.dockerignore
deploy/
├── fable5.service          # PRA-8
└── scripts/
    └── reskin.sh           # PRA-13
deploy.sh                    # PRA-11

requirements-voice.txt       # PRA-6 (adapted: separate file, not pyproject extras — see above)

tests/
├── test_voice_engines.py    # PRA-5
├── test_settings.py         # PRA-9
├── test_api.py              # extended — PRA-10
└── e2e/test_dashboard_screenshot.py  # extended — PRA-12 (no dashboard.js/index.html changes needed, see below)
```

## Integration points

- **`voice/engines.py` is the single source of truth** for STT/TTS availability
  — `face/routes/voice.py` reads `request.app.state.voice` (a `VoiceOS`
  instance set once in `create_app`), never re-implements the availability
  check.
- **PRA-12 turned out to need no dashboard code changes.** Phase 1 already
  built `dashboard.js`'s `refreshVoice()` and `index.html`'s voice panel
  generically against `{stt, tts, state}` field names. Because the real
  `/voice/status` response (PRA-10) kept those exact field names, the
  dashboard already renders live state with zero changes — confirmed by
  extending the existing e2e test rather than by finding UI code to edit.
  Worth stating explicitly so nobody goes looking for dashboard changes that
  don't exist.
- **Config is read once, required lazily.** `config/settings.py` reads
  `ANTHROPIC_API_KEY`/`FABLE5_MODEL` from the environment at import time but
  does not raise if missing — nothing in Phase 1/2 calls the Anthropic API
  yet. `require_anthropic_api_key()` exists for whichever future code path
  first needs it, so the failure is loud and specific at the point of use
  instead of either a silent `None` or a startup crash for an unused key.
- **Deploy modes share one seam**: `deploy.sh` is the only entrypoint a human
  runs; `Dockerfile` and `deploy/fable5.service` are inputs to it, not run
  directly. `reskin.sh` depends on all three being settled first so it copies
  the current file list, not a stale one.

## Sequencing

Matches the Linear `blockedBy` graph exactly:

1. **Parallel, no dependencies**: PRA-5 (voice engine), PRA-7 (Dockerfile),
   PRA-8 (systemd unit), PRA-9 (.env config).
2. **PRA-10** (real voice status/endpoints) — blocked by PRA-5.
3. **PRA-11** (deploy.sh) — blocked by PRA-7, PRA-8.
4. **PRA-12** (dashboard voice UI) — blocked by PRA-10. Turned out to be a
   test-only change (see above).
5. **PRA-13** (reskin.sh) — blocked by PRA-11, PRA-7, PRA-8, last as planned.

No adjustments needed to this ordering — it held up during implementation.

## Agent vs. Human — what actually got built vs. deferred

Per each ticket's flag: the **agent-doable portion of every ticket, including
the two Human-flagged ones, was completed** — PRA-6's `pyproject.toml`/install
plumbing (done as `requirements-voice.txt`) and PRA-8's unit file are both
written and tested where testable. What's still deferred to an actual human,
per those tickets' own Blockers:

- **PRA-6**: installing the real `faster-whisper`/`kokoro-onnx` packages and
  verifying against real audio hardware — this sandbox can't do that; only
  the mocked-import fallback path is verified.
- **PRA-7 / PRA-11 (docker branch)**: `Dockerfile` is written and follows the
  correct entrypoint, but `docker build`/`docker run` weren't actually run —
  no Docker available in this sandbox to verify against.
- **PRA-8 / PRA-11 (systemd branch)**: unit file is written and matches the
  entrypoint, but installing/starting it (`systemctl enable --now`) needs a
  real Linux host with systemd + sudo — this sandbox container has neither.

`./deploy.sh local` **is** fully verified — booted the real app via the script
and confirmed both the dashboard and the new voice endpoints respond
correctly. `reskin.sh` was verified in an isolated temp copy (not this repo)
to confirm it produces the correct rebranded file tree and git-inits cleanly.

## Not covered here

Nothing — all 9 tickets have either a completed, tested implementation or an
explicit note above on exactly what remains for a human to verify on real
hardware/infrastructure.
