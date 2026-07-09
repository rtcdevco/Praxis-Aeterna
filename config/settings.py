"""Central paths and constants for Fable 5 OS."""

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

VAULT_DIR = REPO_ROOT / "vault"
SKILLS_DIR = REPO_ROOT / "skills"
MANIFEST_PATH = REPO_ROOT / "skills_manifest.json"

# Conservative token budget per active-skill context package (see core/context_budget.py).
CONTEXT_TOKEN_BUDGET = 8000

# Runtime LLM tier for skill execution and the routing fallback — deliberately
# cheap/fast (this product's own build guide shows "route -> regex -> local ->
# Haiku" for runtime work; the expensive Opus/Fable-5 tier is reserved for
# *building* this software, not running it).
LLM_MODEL = os.environ.get("FABLE5_LLM_MODEL", "claude-haiku-4-5")
LLM_EXECUTE_MAX_TOKENS = 2048
LLM_ROUTING_MAX_TOKENS = 20
