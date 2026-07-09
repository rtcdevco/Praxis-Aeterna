import httpx
from anthropic import RateLimitError
from fastapi.testclient import TestClient

from face.main import create_app

from ._fake_anthropic import FakeAnthropicClient, fake_message

_REQUEST = httpx.Request("POST", "https://api.anthropic.com/v1/messages")


def _write_skill(skills_dir, name, patterns=(), keywords=(), context_files=None):
    skill_dir = skills_dir / name
    skill_dir.mkdir(parents=True)
    lines = ["---"]
    if patterns:
        lines.append("intent_patterns:")
        lines += [f'  - "{p}"' for p in patterns]
    if keywords:
        lines.append("keywords: [" + ", ".join(keywords) + "]")
    lines.append("priority: 0")
    lines.append("---")
    lines.append("# Skill\n")
    if context_files:
        lines.append("## Context Files")
        for filename, _content in context_files:
            lines.append(f"- {filename} — supporting context")
        lines.append("")
    (skill_dir / "SKILL.md").write_text("\n".join(lines), encoding="utf-8")
    for filename, content in context_files or []:
        (skill_dir / filename).write_text(content, encoding="utf-8")


def _build_client(tmp_path, anthropic_client, context_files=None):
    vault_dir = tmp_path / "vault"
    (vault_dir / "01-daily").mkdir(parents=True)
    (vault_dir / "04-knowledge").mkdir(parents=True)
    (vault_dir / "05-templates").mkdir(parents=True)
    (vault_dir / "05-templates" / "daily.md").write_text("# {{date}}\n", encoding="utf-8")

    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    _write_skill(
        skills_dir,
        "productivity",
        patterns=[r"\\btask\\b"],
        keywords=["task", "todo"],
        context_files=context_files,
    )

    manifest_path = tmp_path / "skills_manifest.json"
    app = create_app(
        vault_dir=vault_dir,
        skills_dir=skills_dir,
        manifest_path=manifest_path,
        anthropic_client=anthropic_client,
    )
    return TestClient(app)


def test_execute_happy_path_builds_budgeted_system_prompt(tmp_path):
    small_content = "small supporting note"
    big_content = "x" * 50_000  # comfortably exceeds the 8000-token budget

    fake_client = FakeAnthropicClient(create_results=[fake_message("Added task: buy milk")])
    client = _build_client(
        tmp_path,
        fake_client,
        context_files=[("small.md", small_content), ("big.md", big_content)],
    )

    response = client.post("/api/skills/execute", json={"utterance": "add a task"})
    assert response.status_code == 200
    body = response.json()
    assert body["matched_skill"] == "productivity"
    assert body["routing_method"] == "deterministic"
    assert body["response"] == "Added task: buy milk"
    assert body["usage"] == {"input_tokens": 10, "output_tokens": 5}

    system_prompt = fake_client.messages.calls[-1]["system"]
    assert small_content in system_prompt
    assert big_content not in system_prompt


def test_execute_llm_routing_fallback_then_executes(tmp_path):
    fake_client = FakeAnthropicClient(
        create_results=[
            fake_message('{"skill": "productivity"}'),  # classify_route call
            fake_message("Noted."),  # execute_skill call
        ]
    )
    client = _build_client(tmp_path, fake_client)

    response = client.post("/api/skills/execute", json={"utterance": "completely unrelated phrasing"})
    assert response.status_code == 200
    body = response.json()
    assert body["matched_skill"] == "productivity"
    assert body["routing_method"] == "llm_fallback"
    assert body["response"] == "Noted."
    assert len(fake_client.messages.calls) == 2


def test_execute_no_match_even_with_llm_configured(tmp_path):
    fake_client = FakeAnthropicClient(create_results=[fake_message('{"skill": "none"}')])
    client = _build_client(tmp_path, fake_client)

    response = client.post("/api/skills/execute", json={"utterance": "asdkjhasdkjh"})
    assert response.status_code == 200
    body = response.json()
    assert body["matched_skill"] is None
    assert body["routing_method"] == "none"
    assert body["response"] is None


def test_execute_rate_limited_returns_429_with_retry_after(tmp_path):
    response_obj = httpx.Response(429, request=_REQUEST, headers={"retry-after": "12"})
    fake_client = FakeAnthropicClient(
        create_results=[RateLimitError("slow down", response=response_obj, body=None)]
    )
    client = _build_client(tmp_path, fake_client)

    response = client.post("/api/skills/execute", json={"utterance": "add a task"})
    assert response.status_code == 429
    detail = response.json()["detail"]
    assert detail["error"] == "rate_limited"
    assert detail["retry_after"] == 12.0


def test_execute_saves_response_to_vault_when_requested(tmp_path):
    fake_client = FakeAnthropicClient(create_results=[fake_message("Task added: buy milk")])
    client = _build_client(tmp_path, fake_client)

    response = client.post(
        "/api/skills/execute",
        json={"utterance": "add a task", "save_to_vault": True, "vault_title": "Milk Task"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["saved_to_vault"] == {"path": "04-knowledge/milk-task.md"}

    search = client.get("/api/vault/search", params={"q": "milk"}).json()
    assert any(r["path"] == "04-knowledge/milk-task.md" for r in search["results"])
