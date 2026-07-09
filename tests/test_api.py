import pytest
from fastapi.testclient import TestClient

from face.main import create_app


def _write_skill(skills_dir, name, patterns=(), keywords=()):
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
    lines.append("# Skill\n\n## Context Files\n")
    (skill_dir / "SKILL.md").write_text("\n".join(lines), encoding="utf-8")


@pytest.fixture
def client(tmp_path):
    vault_dir = tmp_path / "vault"
    (vault_dir / "01-daily").mkdir(parents=True)
    (vault_dir / "05-templates").mkdir(parents=True)
    (vault_dir / "05-templates" / "daily.md").write_text("# {{date}}\n", encoding="utf-8")

    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    _write_skill(skills_dir, "productivity", patterns=[r"\\btask\\b"], keywords=["task", "todo"])

    manifest_path = tmp_path / "skills_manifest.json"

    app = create_app(
        vault_dir=vault_dir, skills_dir=skills_dir, manifest_path=manifest_path, anthropic_client=None
    )
    return TestClient(app)


def test_index_page_served(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "V.A.U.L.T." in response.text


def test_metrics_empty_vault(client):
    response = client.get("/api/metrics")
    assert response.status_code == 200
    body = response.json()
    assert body["vault_nodes"] == 0
    assert body["graph_links"] == 0
    assert body["daily_notes"] == 0
    assert body["active_skill"] is None


def test_skills_list(client):
    response = client.get("/api/skills")
    assert response.json() == {"skills": ["productivity"]}


def test_voice_status_stub(client):
    response = client.get("/api/voice/status")
    body = response.json()
    assert body["stt"] == "unavailable"
    assert body["tts"] == "unavailable"


def test_route_utterance_updates_active_skill_and_metrics(client):
    response = client.post("/api/skills/route", json={"utterance": "add a task"})
    assert response.json() == {"matched_skill": "productivity", "routing_method": "deterministic"}

    metrics = client.get("/api/metrics").json()
    assert metrics["active_skill"] == "productivity"
    assert metrics["context_usage"]["used_tokens"] > 0


def test_route_utterance_no_match(client):
    response = client.post("/api/skills/route", json={"utterance": "completely unrelated"})
    assert response.json() == {"matched_skill": None, "routing_method": "none"}


def test_execute_utterance_without_llm_configured_returns_503(client):
    response = client.post("/api/skills/execute", json={"utterance": "add a task"})
    assert response.status_code == 503
    assert response.json()["detail"]["error"] == "llm_not_configured"


def test_execute_utterance_no_match_returns_empty_without_error(client):
    response = client.post("/api/skills/execute", json={"utterance": "completely unrelated"})
    assert response.status_code == 200
    body = response.json()
    assert body == {
        "matched_skill": None,
        "routing_method": "none",
        "response": None,
        "usage": None,
        "saved_to_vault": None,
    }


def test_save_note_then_appears_in_metrics_and_search(client):
    save_response = client.post(
        "/api/vault/note",
        json={"content": "Body text about widgets.", "folder": "04-knowledge", "title": "Widget Notes"},
    )
    assert save_response.status_code == 200
    assert save_response.json()["path"] == "04-knowledge/widget-notes.md"

    metrics = client.get("/api/metrics").json()
    assert metrics["vault_nodes"] == 1

    search = client.get("/api/vault/search", params={"q": "widgets"}).json()
    assert search["results"][0]["path"] == "04-knowledge/widget-notes.md"


def test_graph_reflects_saved_notes_with_links(client):
    client.post(
        "/api/vault/note",
        json={"content": "See also [[note-b]].", "folder": "04-knowledge", "title": "Note A"},
    )
    client.post(
        "/api/vault/note",
        json={"content": "No links here.", "folder": "04-knowledge", "title": "Note B"},
    )

    graph = client.get("/api/graph").json()
    assert len(graph["nodes"]) == 2
    assert graph["edges"] == [
        {"source": "04-knowledge/note-a.md", "target": "04-knowledge/note-b.md"}
    ]
