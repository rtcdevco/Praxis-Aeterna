# Build Plan — Voice Pipeline Split, Sessions, Skills Gap (Step 03)

Reference input: `Fable5_OS_Architecture.pdf`, a fuller build spec than what had
actually been implemented so far. Comparing it against the real repo surfaced a
concrete gap between the documented five-pillar architecture and the leaner MVP
that had been built. No Linear tickets this pass — consistent with how the
observability pass ended (ticket creation was declined then too); this doc is the
paper trail instead.

## The gap, and what closed it

| Architecture Reference calls for | What existed before this pass | What this pass adds |
|---|---|---|
| `voice/stt_engine.py`, `tts_engine.py`, `audio_capture.py`, `audio_playback.py`, `intent_router.py`, `wake_word.py` | One combined `voice/engines.py` (STT + TTS + VoiceOS) | Six-module split + a `voice_os.py` facade, matching the spec's one-module-per-concern shape |
| `core/context_manager.py`, `core/session.py` | Ad hoc `app.state.active_skill`/`app.state.last_context_package` globals, no session concept | Real `Session`/`SessionManager` (in-memory, per-process) and `ContextManager` (wraps the existing `ContextBudget`), backing one implicit `"default"` session |
| `skills/{content,sales,finance,ops}` | Only `productivity`, `research` | All four added, matching the existing template exactly |
| `config/voice_patterns.json` | Didn't exist | Added, wired via `config.settings.VOICE_PATTERNS_PATH` |

## Adaptations from the literal spec

Same posture as the two earlier passes this session (Voice/Handoff, Observability):
ground the spec in what's actually real and verifiable here, and say so explicitly
where it diverges.

- **`audio_capture.py`/`audio_playback.py`** use `sounddevice` (optional import,
  same graceful-unavailable pattern as STT/TTS) rather than a heavier audio
  framework — there's no microphone or speakers in this sandbox to test against
  regardless, so the specific library choice doesn't change what's verifiable.
  VAD is a real RMS-energy-vs-threshold computation, not a stub — deliberately
  simple rather than pulling in a full VAD model, since a heavier model would be
  another optional dependency this environment still couldn't verify against real
  audio.
- **`wake_word.py`** does not add a dedicated wake-word/keyword-spotting engine
  dependency (e.g. a proprietary SDK). It reuses `STTEngine`, which is already
  part of the pipeline: transcribe a short buffer, check whether the wake phrase
  appears in the text. No new dependency, and honestly scoped to what's actually
  testable here (mocked STT) versus what isn't (real-time audio processing
  latency, which a dedicated wake-word model would optimize for and this
  approach doesn't).
- **Sessions are wired but only one is used.** `SessionManager`/`ContextManager`
  are real, tested, and support multiple concurrent sessions — but no route
  currently accepts a `session_id` from the caller, so `face/main.py` backs a
  single implicit `"default"` session. This preserves the existing single-user
  route contracts (`/api/skills/route`, `/api/metrics` — response shapes
  unchanged) while giving future multi-session work a real foundation instead of
  a globals-based one. Extending routes to accept a real session identifier is
  the natural next step if multi-session support is ever actually needed.
  **Update (2026-07-23): this has since been done** — see the Addendum at the end of this document.

## File structure (additions/changes only)

```
voice/
├── stt_engine.py       # moved from engines.py, unchanged
├── tts_engine.py        # moved from engines.py, unchanged
├── voice_os.py           # moved from engines.py, unchanged (imports the two above)
├── audio_capture.py       # new
├── audio_playback.py       # new
├── intent_router.py         # new
└── wake_word.py               # new

core/
├── session.py            # new: Session, SessionManager, DEFAULT_SESSION_ID
└── context_manager.py     # new: ContextManager (wraps ContextBudget)

skills/
├── content/SKILL.md + calendar.md    # new
├── sales/SKILL.md + pipeline.md       # new
├── finance/SKILL.md + ledger.md        # new
└── ops/SKILL.md + runbook.md            # new

config/voice_patterns.json   # new
```

## Integration points

- **`face/main.py`** is the only place that constructs `SessionManager`/
  `ContextManager` and wires them onto `app.state`. The metrics-recording
  middleware now also touches the default session on every request, so
  `Session.last_active_at` reflects real traffic.
- **`face/routes/skills.py`** and **`face/routes/metrics.py`** were updated to
  read/write through `context_manager` (scoped to `DEFAULT_SESSION_ID`) instead of
  raw `app.state` fields — the external JSON contracts (`{"matched_skill": ...}`,
  the `active_skill`/`context_usage` fields in `/api/metrics`) are byte-for-byte
  unchanged, confirmed by the existing tests passing without modification.
- **`intent_router.py`'s `IntentRouter` does not reimplement routing** — it wraps
  the existing `core.router.SkillRouter`, so a voice transcript and a typed
  utterance are routed by the exact same regex-then-keyword logic. The only
  voice-specific behavior is wake-phrase stripping before routing.
- **`observability/health_aggregator.py`** required a one-line import-path fix
  (`voice.engines` → `voice.voice_os`) and a version-header bump per its own
  audit convention (`# version: 2`) — a good real-world exercise of the audit
  log's actual purpose from the previous pass.

## Verification

- 112 tests passing (up from 81 before this pass): new coverage in
  `tests/test_voice_pipeline.py` (audio capture/playback, intent routing,
  wake-word), `tests/test_session.py`, `tests/test_context_manager.py`, plus
  `tests/test_voice_engines.py` updated for the new import paths.
- `ruff check` clean on every file touched this pass (pre-existing lint debt in
  untouched files, e.g. `tests/test_router.py`, intentionally left alone — same
  policy as the prior two passes).
- Smoke-tested against the real running app via `./deploy.sh local`: confirmed
  `/api/skills` lists all 6 skills, `/api/health/score` reports "6 skill(s)
  loaded," and — after an initial phrasing that didn't match my own regex — each
  new skill's intent pattern verified against a correctly-matching utterance
  ("log a lead" → sales, "add a deal" → sales, "monthly spend" → finance,
  "system status" → ops, "draft a post" → content).

## Not covered here

- Real audio hardware verification (mic capture, speaker playback, wake-word
  latency) — same limitation as the Voice/Handoff pass; this sandbox has no audio
  hardware.
- ~~Exposing session IDs through the API so multiple real sessions can be
  used concurrently — the primitives exist, but no route accepts one yet.~~
  Closed 2026-07-23 — see the Addendum below.

## Addendum (2026-07-23) — session_id exposed through the API

`/api/skills/route` (JSON body field), `/api/metrics`, `/api/voice/command`,
and `/api/voice/listen` (query param on all three) now accept an optional
`session_id`, defaulting to `core.session.DEFAULT_SESSION_ID`. No response
shape changed and no existing route contract changed — every pre-existing
test in `tests/test_api.py` still passes unmodified, since omitting
`session_id` reproduces exactly the old hardcoded-`DEFAULT_SESSION_ID`
behavior. `core/session.py` and `core/context_manager.py` needed no changes;
they already supported arbitrary session ids, per the original note above.
