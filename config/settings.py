"""Central paths and constants for Fable 5 OS."""

import os
from pathlib import Path

try:
    from dotenv import load_dotenv  # type: ignore

    load_dotenv()
except ImportError:
    pass  # python-dotenv is optional in prod, where real env vars are already set

REPO_ROOT = Path(__file__).resolve().parent.parent

VAULT_DIR = REPO_ROOT / "vault"
SKILLS_DIR = REPO_ROOT / "skills"
MANIFEST_PATH = REPO_ROOT / "skills_manifest.json"

# Conservative token budget per active-skill context package (see core/context_budget.py).
CONTEXT_TOKEN_BUDGET = 8000

# Read at import time so failures surface immediately in logs, but never raised
# here: nothing in Phase 1/2 calls the Anthropic API yet, so a missing key
# shouldn't break app startup. Callers that actually need it call
# require_anthropic_api_key() instead, which raises loudly at the point of use.
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
FABLE5_MODEL = os.environ.get("FABLE5_MODEL", "claude-sonnet-5")


def require_anthropic_api_key() -> str:
    """Raise a clear, actionable error if ANTHROPIC_API_KEY isn't set.

    Call this from whichever code path first actually needs to call the
    Anthropic API, rather than assuming ANTHROPIC_API_KEY is present.
    """
    if not ANTHROPIC_API_KEY:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set. Copy .env.example to .env and fill "
            "it in, or export ANTHROPIC_API_KEY in your environment."
        )
    return ANTHROPIC_API_KEY
