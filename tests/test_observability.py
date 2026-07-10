import sqlite3
import time

import pytest

from core.manifest import generate_manifest
from core.router import SkillRouter
from observability.drift_detector import DriftDetector
from observability.health_aggregator import HealthAggregator
from observability.metrics_collector import MetricsCollector
from observability.repair_trigger import RepairTrigger
from observability.version_audit import VersionAuditLog, compute_file_hash, read_version_header
from vault_connector.connector import VaultConnector
from voice.engines import VoiceOS


@pytest.fixture
def collector(tmp_path):
    c = MetricsCollector(tmp_path / "metrics.db", retention_days=30)
    yield c
    c.close()


def test_metrics_collector_records_and_summarizes(collector):
    collector.record_request("/api/skills", "GET", duration_ms=12.5, status_code=200)
    collector.record_request("/api/voice/status", "GET", duration_ms=8.0, status_code=200)
    collector.record_request("/api/skills", "GET", duration_ms=500.0, status_code=500)

    summary = collector.summary()
    assert summary["total_requests"] == 3
    assert summary["error_count"] == 1
    assert summary["error_rate"] == pytest.approx(1 / 3)
    assert summary["voice_requests"] == 1
    assert summary["avg_latency_ms"] == pytest.approx((12.5 + 8.0 + 500.0) / 3)


def test_metrics_collector_prunes_old_rows(tmp_path):
    c = MetricsCollector(tmp_path / "metrics.db", retention_days=30)
    with sqlite3.connect(tmp_path / "metrics.db") as conn:
        old_ts = time.time() - 40 * 86400
        conn.execute(
            "INSERT INTO request_metrics (ts, path, method, duration_ms, status_code) "
            "VALUES (?, '/x', 'GET', 1.0, 200)",
            (old_ts,),
        )
        conn.commit()

    c.record_request("/api/skills", "GET", duration_ms=1.0, status_code=200)
    assert c.summary()["total_requests"] == 1  # old row pruned, only the fresh one remains
    c.close()


def test_prometheus_text_format(collector):
    collector.record_request("/api/skills", "GET", duration_ms=10.0, status_code=200)
    text = collector.prometheus_text()
    assert "fable5_requests_total 1" in text
    assert "# TYPE fable5_requests_total counter" in text


def test_sample_memory_returns_positive_kb(collector):
    rss = collector.sample_memory()
    assert rss > 0


def test_drift_detector_flags_latency_spike(collector):
    detector = DriftDetector(collector, sigma_threshold=2.0)
    for _ in range(10):
        collector.record_request("/api/skills", "GET", duration_ms=10.0, status_code=200)
    collector.record_request("/api/skills", "GET", duration_ms=1000.0, status_code=200)

    incident = detector.check_latency_drift(sample_size=20)
    assert incident is not None
    assert incident.kind == "latency_spike"
    assert detector.recent_incidents()[0]["id"] == incident.id


def test_drift_detector_no_incident_when_stable(collector):
    detector = DriftDetector(collector, sigma_threshold=2.0)
    for _ in range(15):
        collector.record_request("/api/skills", "GET", duration_ms=10.0, status_code=200)

    assert detector.check_latency_drift(sample_size=20) is None


def test_drift_detector_flags_error_clustering(collector):
    detector = DriftDetector(collector, sigma_threshold=2.0)
    for _ in range(150):
        collector.record_request("/api/skills", "GET", duration_ms=10.0, status_code=200)
    for _ in range(20):
        collector.record_request("/api/skills", "GET", duration_ms=10.0, status_code=500)

    incident = detector.check_error_clustering(window=20, baseline_window=200)
    assert incident is not None
    assert incident.kind == "error_clustering"


def test_read_version_header(tmp_path):
    f = tmp_path / "sample.py"
    f.write_text("# version: 3\n# changed: 2026-07-09 | Claude | did a thing\nprint(1)\n")
    version, changed = read_version_header(f)
    assert version == 3
    assert changed == "2026-07-09 | Claude | did a thing"


def test_read_version_header_missing():
    version, changed = read_version_header(__file__)
    assert version is None
    assert changed is None


def test_version_audit_record_and_check(tmp_path):
    f = tmp_path / "sample.py"
    f.write_text("# version: 1\n# changed: today | Claude | initial\nprint(1)\n")

    conn = sqlite3.connect(tmp_path / "audit.db")
    log = VersionAuditLog(conn)

    log.record_change(f, author="Claude", description="initial")
    assert log.check_version_bumped(f) is True  # unchanged since recording

    f.write_text("# version: 1\n# changed: today | Claude | forgot to bump\nprint(2)\n")
    assert log.check_version_bumped(f) is False  # content changed, version didn't

    f.write_text("# version: 2\n# changed: today | Claude | bumped correctly\nprint(2)\n")
    assert log.check_version_bumped(f) is True

    conn.close()


def test_version_audit_rejects_file_without_header(tmp_path):
    f = tmp_path / "no_header.py"
    f.write_text("print(1)\n")
    conn = sqlite3.connect(tmp_path / "audit.db")
    log = VersionAuditLog(conn)
    with pytest.raises(ValueError, match="no '# version: N' header"):
        log.record_change(f, author="Claude", description="x")
    conn.close()


def test_compute_file_hash_changes_with_content(tmp_path):
    f = tmp_path / "a.txt"
    f.write_text("hello")
    h1 = compute_file_hash(f)
    f.write_text("hello world")
    h2 = compute_file_hash(f)
    assert h1 != h2


def test_repair_trigger_should_repair_on_declining_trend(tmp_path):
    conn = sqlite3.connect(tmp_path / "repair.db")
    trigger = RepairTrigger(conn, consecutive_threshold=3)

    trigger.record_score(1.0)
    trigger.record_score(0.8)
    assert trigger.should_repair() is False  # only 2 samples

    trigger.record_score(0.6)
    assert trigger.should_repair() is True  # 1.0 -> 0.8 -> 0.6, strictly declining

    conn.close()


def test_repair_trigger_no_repair_when_stable(tmp_path):
    conn = sqlite3.connect(tmp_path / "repair.db")
    trigger = RepairTrigger(conn, consecutive_threshold=3)
    trigger.record_score(0.8)
    trigger.record_score(0.8)
    trigger.record_score(0.8)
    assert trigger.should_repair() is False
    conn.close()


def test_repair_trigger_attempt_repair_logs_result(tmp_path):
    conn = sqlite3.connect(tmp_path / "repair.db")
    trigger = RepairTrigger(conn, consecutive_threshold=3)

    calls = []

    def fix_memory():
        calls.append("fixed")

    fix_memory.__name__ = "reinit_memory"

    result = trigger.attempt_repair(
        unhealthy_components=["memory"],
        repair_actions={"memory": fix_memory},
        score_before=0.6,
        score_after_fn=lambda: 0.8,
    )

    assert result.triggered is True
    assert result.component == "memory"
    assert result.score_after == 0.8
    assert calls == ["fixed"]
    assert trigger.repair_history()[0]["component"] == "memory"
    conn.close()


def _make_aggregator(tmp_path):
    vault_dir = tmp_path / "vault"
    (vault_dir / "01-daily").mkdir(parents=True)
    (vault_dir / "05-templates").mkdir(parents=True)

    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    skill_dir = skills_dir / "productivity"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        "---\nintent_patterns: []\nkeywords: [task]\npriority: 0\n---\n# Productivity\n",
        encoding="utf-8",
    )

    manifest = generate_manifest(skills_dir, tmp_path / "skills_manifest.json")
    router = SkillRouter(manifest, repo_root=tmp_path)
    vault = VaultConnector(vault_dir)
    voice_os = VoiceOS()
    return HealthAggregator(router, vault, voice_os, repo_root=tmp_path)


def test_health_aggregator_all_healthy_on_fresh_repo(tmp_path):
    # deploy assets don't exist under tmp_path, so `handoff` is expected unhealthy here
    aggregator = _make_aggregator(tmp_path)
    report = aggregator.report()
    assert report["score"] == pytest.approx(4 / 5)
    assert report["components"]["handoff"]["healthy"] is False
    assert report["components"]["brain"]["healthy"] is True
    assert report["components"]["memory"]["healthy"] is True
    assert report["components"]["voice"]["healthy"] is True


def test_health_aggregator_report_survives_voice_status_raising(tmp_path):
    """Regression test: report() used to call voice_os.status() a second,
    unprotected time (for voice_engines_available) after check_voice() already
    handled the same exception — a broken voice engine crashed the whole
    report instead of degrading gracefully.
    """
    aggregator = _make_aggregator(tmp_path)
    aggregator.voice_os.status = lambda: (_ for _ in ()).throw(RuntimeError("voice down"))

    report = aggregator.report()  # must not raise
    assert report["components"]["voice"]["healthy"] is False
    assert report["voice_engines_available"] == {"stt": None, "tts": None}


def test_repair_trigger_no_action_for_unregistered_component(tmp_path):
    conn = sqlite3.connect(tmp_path / "repair.db")
    trigger = RepairTrigger(conn, consecutive_threshold=3)
    result = trigger.attempt_repair(
        unhealthy_components=["handoff"],
        repair_actions={},
        score_before=0.6,
        score_after_fn=lambda: 0.6,
    )
    assert result.triggered is False
    conn.close()
