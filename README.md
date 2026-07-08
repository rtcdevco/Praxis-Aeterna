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
| The Voice | Local STT + TTS | 🔜 fast-follow |
| The Handoff | Deploy + client-reskin scripts | 🔜 fast-follow |

Voice and Handoff are deliberately out of scope for this phase: this sandbox
has no microphone/speakers to verify real STT/TTS against, and Docker/systemd
deploy modes can't be meaningfully verified running inside a container either.
Both land as their own PRs once there's a real environment to test them in.

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
- **`docs/fable5/`** — the methodology's step-by-step templates (unrelated to
  the product code above; describes *how* work happens in this repo).

## Getting started

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

uvicorn face.main:app --reload
```

Then open http://127.0.0.1:8000 for the V.A.U.L.T. dashboard.

## Tests

```bash
pytest
```

Unit tests cover the skill router, context budget, vault connector, and
wikilink graph in isolation (pure Python, no external services). `test_api.py`
exercises every `/api/*` route via FastAPI's `TestClient`. `tests/e2e/` drives
a real headless-Chromium session against a seeded vault and asserts the
dashboard renders the actual seeded numbers — proof the full stack is wired
correctly, not just unit-correct in isolation.
