"""Anthropic SDK integration: client construction, skill execution, and the
LLM routing fallback.

Everything here degrades to a safe "not configured" / None outcome when no
API key is present, or to a typed error outcome when a call fails — nothing
in this module raises past its own boundary for network-shaped errors.
Callers (face/routes/skills.py) turn outcomes into HTTP responses.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass

import anthropic


def build_client() -> anthropic.Anthropic | None:
    """A real client if ANTHROPIC_API_KEY is set, else None (graceful degrade)."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return None
    return anthropic.Anthropic()


def build_system_prompt(
    skill_md_text: str,
    context_files: list[tuple[str, str]],
    included_files: set[str],
) -> str:
    """skill_md (mandatory) plus only the context files ContextBudget included."""
    parts = [skill_md_text]
    for name, content in context_files:
        if name in included_files:
            parts.append(f"\n\n---\n# Context: {name}\n\n{content}")
    return "".join(parts)


@dataclass
class SkillExecutionResult:
    text: str
    model: str
    input_tokens: int
    output_tokens: int


@dataclass
class SkillExecutionError:
    kind: str  # "rate_limited" | "timeout" | "connection_error" | "upstream_error" | "refused"
    message: str
    retry_after: float | None = None


def execute_skill(
    client: anthropic.Anthropic,
    model: str,
    system_prompt: str,
    utterance: str,
    max_tokens: int,
) -> SkillExecutionResult | SkillExecutionError:
    try:
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": utterance}],
        )
    except anthropic.RateLimitError as e:
        retry_after = None
        try:
            retry_after = float(e.response.headers.get("retry-after", "")) or None
        except (TypeError, ValueError, AttributeError):
            retry_after = None
        return SkillExecutionError("rate_limited", str(e), retry_after=retry_after)
    except anthropic.APITimeoutError as e:
        return SkillExecutionError("timeout", str(e))
    except anthropic.APIConnectionError as e:
        return SkillExecutionError("connection_error", str(e))
    except anthropic.APIStatusError as e:
        return SkillExecutionError("upstream_error", f"{e.status_code}: {e.message}")

    if response.stop_reason == "refusal":
        return SkillExecutionError("refused", "The model declined to respond to this request.")

    text = next((block.text for block in response.content if block.type == "text"), "")
    return SkillExecutionResult(
        text=text,
        model=response.model,
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
    )


def classify_route(
    client: anthropic.Anthropic,
    model: str,
    utterance: str,
    skill_names: list[str],
    max_tokens: int,
) -> str | None:
    """Ask Claude to pick a skill when the deterministic router found none.

    Fails closed: any error, refusal, unparseable body, or an out-of-set
    answer all return None — identical to "no match" from SkillRouter.route().
    """
    if not skill_names:
        return None

    schema = {
        "type": "object",
        "properties": {"skill": {"type": "string", "enum": [*skill_names, "none"]}},
        "required": ["skill"],
        "additionalProperties": False,
    }
    prompt = (
        "You are the routing classifier for a personal-assistant app. Given the "
        "user's message, choose the single skill that best handles it, or "
        '"none" if no skill applies. Do not invent a skill name outside the '
        "given list.\n\n"
        f"Available skills: {', '.join(skill_names)}\n\n"
        f"User message: {utterance}"
    )

    try:
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            output_config={"format": {"type": "json_schema", "schema": schema}},
            messages=[{"role": "user", "content": prompt}],
        )
    except anthropic.APIError:
        return None

    if response.stop_reason == "refusal":
        return None

    text = next((block.text for block in response.content if block.type == "text"), None)
    if text is None:
        return None
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None

    skill = data.get("skill")
    return skill if skill in skill_names else None  # defense-in-depth beyond the enum
