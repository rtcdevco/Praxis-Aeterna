# Fable 5 OS

A local, voice-driven AI command center — modular skills, an Obsidian-compatible
memory vault, local voice, and a unified V.A.U.L.T. dashboard, all in one repo.
Built with the [Fable 5 methodology](./CLAUDE.md): Sonnet 5 brainstorms it,
Linear structures it, Fable 5 plans it, Opus-tier agents build it.

## Five pillars

| Pillar | Component | Status |
|---|---|---|
| The Brain | Skill router + real Claude-powered execution (`core/`) | ✅ Phase 1 + 2 |
| The Memory | Obsidian-compatible vault (`vault_connector/`) | ✅ Phase 1 |
| The Face | FastAPI + V.A.U.L.T. dashboard (`face/`) | ✅ Phase 1 |
| The Voice | Local STT + TTS | 🔜 fast-follow |
| The Handoff | Deploy + client-reskin scripts | 🔜 fast-follow |

Voice and Handoff are deliberately out of scope for this phase: this sandbox
has no microphone/speakers to verify real STT/TTS against, and Docker/systemd
deploy modes can't be meaningfully verified running inside a container either.
Both land as their own PRs once there's a real environment to test them in.

## What's here

- **`core/`** — skill discovery + manifest generation, a two-phase
  (regex-then-keyword, then an LLM fallback when a live API key is
  configured) intent router, a token-budget-aware context assembler, and
  (`core/llm.py`) the real Claude call that actually executes a matched
  skill.
- **`vault_connector/`** — reads/writes the `vault/` directory (plain Markdown
  + `[[wikilinks]]`, no database): scanning, saving notes, scored search, a
  wikilink knowledge graph, and daily-note templating.
- **`face/`** — a FastAPI backend and a static (no-build-step) dashboard that
  polls it, showing live metrics, the skill list, voice status, and a
  D3 force-directed graph of the vault. `POST /api/skills/execute` routes an
  utterance, calls Claude with the skill's budgeted context, and can save the
  response straight to the vault.
- **`skills/`** — starter skills (`productivity`, `research`, `content`,
  `sales`, `finance`, `ops`), each a self-contained folder with a `SKILL.md`
  definition.
- **`vault/`** — the Obsidian-compatible data directory (`00-inbox` through
  `06-archive`); most subfolders are gitignored at the content level so your
  own notes don't get committed, only the structure does.
- **`docs/fable5/`** — the methodology's step-by-step templates (unrelated to
  the product code above; describes *how* work happens in this repo).

## Getting started

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Optional — without this, skill execution returns 503 and routing falls
# back to keyword-matching only (no LLM in the loop).
cp .env.example .env
# then edit .env and set ANTHROPIC_API_KEY

uvicorn face.main:app --reload
```

`.env` is loaded automatically (via `config/settings.py`) and is gitignored, so
your key never gets committed. A real environment variable always wins over
`.env` if both are set — handy for CI/production, where secrets come from the
platform rather than a file.

Then open http://127.0.0.1:8000 for the V.A.U.L.T. dashboard.

## Tests

```bash
pytest
```

Unit tests cover the skill router, context budget, vault connector, wikilink
graph, and the Anthropic client wrapper in isolation (pure Python, no real
network calls — `core/llm.py` is tested against a fake Anthropic client
double). `test_api.py` and `test_skills_execute_api.py` exercise every
`/api/*` route via FastAPI's `TestClient`, including the LLM routing fallback
and skill-execution error mapping. `tests/e2e/` drives a real headless-Chromium
session against a seeded vault and asserts the dashboard renders the actual
seeded numbers — proof the full stack is wired correctly, not just
unit-correct in isolation. CI (`.github/workflows/ci.yml`) runs the full suite
on every push and PR.
