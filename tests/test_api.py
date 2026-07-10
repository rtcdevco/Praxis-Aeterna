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
    observability_db_path = tmp_path / "observability.db"

    app = create_app(
        vault_dir=vault_dir,
        skills_dir=skills_dir,
        manifest_path=manifest_path,
        observability_db_path=observability_db_path,
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


def test_voice_status_unavailable_without_deps(client):
    response = client.get("/api/voice/status")
    body = response.json()
    assert body["stt"] == "unavailable"
    assert body["tts"] == "unavailable"
    assert body["state"] == "idle"


def test_voice_transcribe_without_deps_returns_clear_error(client):
    response = client.post(
        "/api/voice/transcribe",
        files={"file": ("clip.wav", b"not-real-audio", "audio/wav")},
    )
    assert response.status_code == 200
    assert response.json() == {"text": "", "error": "faster-whisper not installed"}


def test_voice_synthesize_without_deps_returns_clear_error(client):
    response = client.post("/api/voice/synthesize", json={"text": "hello there"})
    assert response.status_code == 200
    assert response.json() == {"path": None, "error": "kokoro-onnx not installed"}


def test_route_utterance_updates_active_skill_and_metrics(client):
    response = client.post("/api/skills/route", json={"utterance": "add a task"})
    assert response.json() == {"matched_skill": "productivity"}

    metrics = client.get("/api/metrics").json()
    assert metrics["active_skill"] == "productivity"
    assert metrics["context_usage"]["used_tokens"] > 0


def test_route_utterance_no_match(client):
    response = client.post("/api/skills/route", json={"utterance": "completely unrelated"})
    assert response.json() == {"matched_skill": None}


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


def test_observability_metrics_prometheus_format(client):
    client.get("/api/skills")  # generate at least one recorded request
    response = client.get("/api/observability/metrics")
    assert response.status_code == 200
    assert "fable5_requests_total" in response.text
    assert "# TYPE fable5_requests_total counter" in response.text


def test_health_score_all_healthy_by_default(client):
    response = client.get("/api/health/score")
    body = response.json()
    assert body["score"] == 1.0
    assert body["components"]["brain"]["healthy"] is True
    assert body["components"]["memory"]["healthy"] is True
    assert body["components"]["face"]["healthy"] is True
    assert body["components"]["voice"]["healthy"] is True
    assert body["components"]["handoff"]["healthy"] is True
    assert body["repair"] is None


def test_observability_incidents_empty_with_little_traffic(client):
    response = client.get("/api/observability/incidents")
    assert response.json() == {"incidents": []}


def test_audit_log_empty_by_default(client):
    response = client.get("/api/audit/log")
    assert response.json() == {"entries": []}


def test_health_score_repairs_after_declining_trend(client):
    app_state = client.app.state

    baseline = client.get("/api/health/score").json()
    assert baseline["score"] == 1.0

    # Break the vault so `memory` reports unhealthy, then break voice too —
    # two successive checks with a strictly worsening score.
    real_scan = app_state.vault.scan_vault

    def flaky_scan(force_rescan=False):
        if force_rescan:
            app_state.vault.scan_vault = real_scan  # simulate the repair "fixing" it
            return real_scan(force_rescan=force_rescan)
        raise RuntimeError("simulated vault failure")

    app_state.vault.scan_vault = flaky_scan
    second = client.get("/api/health/score").json()
    assert second["components"]["memory"]["healthy"] is False
    assert second["score"] == pytest.approx(0.8)

    app_state.voice.status = lambda: (_ for _ in ()).throw(RuntimeError("voice down"))
    third = client.get("/api/health/score").json()

    assert third["repair"] is not None
    assert third["repair"]["component"] == "memory"
    assert third["repair"]["score_before"] == pytest.approx(0.6)
    # Memory got fixed by the repair action; voice is still broken (untouched),
    # so the post-repair score reflects partial recovery, not a full fix. The
    # top-level `score` is computed fresh *after* repair runs, so it matches
    # score_after rather than the pre-repair score that triggered it.
    assert third["repair"]["score_after"] == pytest.approx(0.8)
    assert third["score"] == pytest.approx(0.8)
    assert third["components"]["memory"]["healthy"] is True
    assert third["components"]["voice"]["healthy"] is False

    audit_after = client.get("/api/audit/log").json()
    assert audit_after == {"entries": []}  # repair doesn't touch the version-audit log
