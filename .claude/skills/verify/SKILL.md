---
description: Launch and drive Fable 5 OS (FastAPI app) for verification/manual testing
---

# Verify — Fable 5 OS

Single-package FastAPI app. venv is usually already set up in this repo's
sessions; if not:

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## Launch (background)

```bash
source .venv/bin/activate
rm -f skills_manifest.json observability_data.db   # stale generated files from a prior run
nohup uvicorn face.main:app --host 127.0.0.1 --port <PORT> &> /tmp/server.log &
echo $! > /tmp/server.pid
for i in {1..20}; do curl -sf http://127.0.0.1:<PORT>/api/skills > /dev/null && break; sleep 0.5; done
```

Use a non-default port (e.g. 8010) if another session's server might still be
running on 8000 — nothing enforces single-instance.

## Drive it

- `GET /api/skills` — lists all skill folders under `skills/` (6 as of this
  writing: productivity, research, content, sales, finance, ops).
- `POST /api/skills/route -d '{"utterance":"..."}'` — routes text through the
  regex-then-keyword `SkillRouter`; sets the session's active skill.
- `GET /api/metrics` — reflects `active_skill` set by the route above (via
  `ContextManager`, not a raw global) plus vault/graph counts.
- `POST /api/vault/note -d '{"content":"...","folder":"04-knowledge","title":"..."}'`
  — saves a note. **Wikilinks resolve by filename stem, not by title** — link
  text must match the slug (`[[second-note]]`), not the human title
  (`[[Second Note]]`), or no graph edge is created. This bit me once; it's
  intended Phase-1 behavior, not a bug.
- `GET /api/graph` — nodes/edges from wikilinks.
- `GET /api/voice/status`, `POST /api/voice/transcribe` (multipart `file=`),
  `POST /api/voice/synthesize -d '{"text":"..."}'`, `POST /api/voice/command`
  (multipart `file=` — transcribe + route through `IntentRouter`/
  `WakeWordDetector`, updates the active skill same as `/api/skills/route`),
  `POST /api/voice/listen` (mic capture via `AudioCapture` → VAD gate → same
  routing → optional spoken confirmation via `AudioPlayback`) — all degrade
  gracefully to `{"error": "... not installed"}` unless `requirements-voice.txt`
  is installed (it isn't, normally — no real mic/speakers in this environment
  anyway).
- `GET /api/health/score` — composite health across the 5 pillars; self-repair
  fires automatically after 3 consecutive declining checks (no separate
  trigger to call).
- `GET /api/observability/metrics` (Prometheus text), `GET
  /api/observability/incidents`, `GET /api/audit/log`.

**Resolved gap:** as of the follow-up pass that added `/api/voice/command` and
`/api/voice/listen`, `audio_capture.py`, `audio_playback.py`,
`intent_router.py`, and `wake_word.py` are no longer inert — `voice_os.py`
composes all of them and `face/main.py` constructs `IntentRouter` from the
real `config/voice_patterns.json` at startup. Confirmed via the same AST-scan
technique that originally caught the gap: every one of the five names
(`AudioCapture`, `AudioPlayback`, `IntentRouter`, `WakeWordDetector`,
`load_voice_patterns`) now resolves to a real caller (`voice/voice_os.py` or
`face/main.py`), not zero.

## Stop

```bash
kill $(cat /tmp/server.pid)
rm -f skills_manifest.json observability_data.db   # don't commit generated files
```
