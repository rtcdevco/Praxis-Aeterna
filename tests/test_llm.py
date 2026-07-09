import httpx
from anthropic import APIConnectionError, APIStatusError, APITimeoutError, RateLimitError

from core.llm import (
    SkillExecutionError,
    SkillExecutionResult,
    build_system_prompt,
    classify_route,
    execute_skill,
)

from ._fake_anthropic import FakeAnthropicClient, fake_message

_REQUEST = httpx.Request("POST", "https://api.anthropic.com/v1/messages")


def test_build_system_prompt_includes_skill_md_and_only_included_files():
    prompt = build_system_prompt(
        "# Skill body",
        [("a.md", "content A"), ("b.md", "content B")],
        included_files={"a.md"},
    )
    assert "# Skill body" in prompt
    assert "content A" in prompt
    assert "content B" not in prompt


def test_build_system_prompt_with_no_context_files():
    prompt = build_system_prompt("# Skill body", [], included_files=set())
    assert prompt == "# Skill body"


def test_execute_skill_happy_path():
    client = FakeAnthropicClient(create_results=[fake_message("Added task: buy milk")])
    result = execute_skill(client, "claude-haiku-4-5", "system prompt", "add a task", 2048)

    assert isinstance(result, SkillExecutionResult)
    assert result.text == "Added task: buy milk"
    assert result.input_tokens == 10
    assert result.output_tokens == 5
    assert client.messages.calls[0]["model"] == "claude-haiku-4-5"
    assert client.messages.calls[0]["system"] == "system prompt"


def test_execute_skill_refusal():
    client = FakeAnthropicClient(create_results=[fake_message("", stop_reason="refusal")])
    result = execute_skill(client, "claude-haiku-4-5", "system", "utterance", 2048)

    assert isinstance(result, SkillExecutionError)
    assert result.kind == "refused"


def test_execute_skill_rate_limited_extracts_retry_after():
    response = httpx.Response(429, request=_REQUEST, headers={"retry-after": "30"})
    client = FakeAnthropicClient(create_results=[RateLimitError("rate limited", response=response, body=None)])
    result = execute_skill(client, "claude-haiku-4-5", "system", "utterance", 2048)

    assert isinstance(result, SkillExecutionError)
    assert result.kind == "rate_limited"
    assert result.retry_after == 30.0


def test_execute_skill_timeout():
    client = FakeAnthropicClient(create_results=[APITimeoutError(request=_REQUEST)])
    result = execute_skill(client, "claude-haiku-4-5", "system", "utterance", 2048)
    assert isinstance(result, SkillExecutionError)
    assert result.kind == "timeout"


def test_execute_skill_connection_error():
    client = FakeAnthropicClient(create_results=[APIConnectionError(message="conn error", request=_REQUEST)])
    result = execute_skill(client, "claude-haiku-4-5", "system", "utterance", 2048)
    assert isinstance(result, SkillExecutionError)
    assert result.kind == "connection_error"


def test_execute_skill_upstream_error():
    response = httpx.Response(500, request=_REQUEST)
    client = FakeAnthropicClient(create_results=[APIStatusError("server error", response=response, body=None)])
    result = execute_skill(client, "claude-haiku-4-5", "system", "utterance", 2048)
    assert isinstance(result, SkillExecutionError)
    assert result.kind == "upstream_error"


def test_classify_route_returns_valid_skill():
    client = FakeAnthropicClient(create_results=[fake_message('{"skill": "research"}')])
    result = classify_route(client, "claude-haiku-4-5", "look into X", ["productivity", "research"], 20)
    assert result == "research"


def test_classify_route_returns_none_for_out_of_set_skill():
    client = FakeAnthropicClient(create_results=[fake_message('{"skill": "not_a_real_skill"}')])
    result = classify_route(client, "claude-haiku-4-5", "utterance", ["productivity", "research"], 20)
    assert result is None


def test_classify_route_returns_none_on_unparseable_response():
    client = FakeAnthropicClient(create_results=[fake_message("not json")])
    result = classify_route(client, "claude-haiku-4-5", "utterance", ["productivity"], 20)
    assert result is None


def test_classify_route_returns_none_on_refusal():
    client = FakeAnthropicClient(create_results=[fake_message('{"skill": "none"}', stop_reason="refusal")])
    result = classify_route(client, "claude-haiku-4-5", "utterance", ["productivity"], 20)
    assert result is None


def test_classify_route_returns_none_on_api_error():
    response = httpx.Response(500, request=_REQUEST)
    client = FakeAnthropicClient(create_results=[APIStatusError("boom", response=response, body=None)])
    result = classify_route(client, "claude-haiku-4-5", "utterance", ["productivity"], 20)
    assert result is None


def test_classify_route_with_no_skills_returns_none():
    client = FakeAnthropicClient()
    result = classify_route(client, "claude-haiku-4-5", "utterance", [], 20)
    assert result is None
    assert client.messages.calls == []
