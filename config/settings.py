"""Central paths and constants for Fable 5 OS."""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

VAULT_DIR = REPO_ROOT / "vault"
SKILLS_DIR = REPO_ROOT / "skills"
MANIFEST_PATH = REPO_ROOT / "skills_manifest.json"

# Conservative token budget per active-skill context package (see core/context_budget.py).
CONTEXT_TOKEN_BUDGET = 8000
