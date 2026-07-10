"""End-to-end proof that the full stack (manifest -> connector -> FastAPI ->
static JS -> D3) is wired correctly, not just unit-correct in isolation:
launches the real app against seeded fixture data and asserts the dashboard
renders the actual seeded numbers.
"""

from __future__ import annotations

import multiprocessing
import socket
import time
import urllib.request

import pytest
from playwright.sync_api import sync_playwright

CHROMIUM_PATH = "/opt/pw-browsers/chromium"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _run_server(vault_dir: str, skills_dir: str, manifest_path: str, port: int) -> None:
    import uvicorn

    from face.main import create_app
    from pathlib import Path

    app = create_app(
        vault_dir=Path(vault_dir), skills_dir=Path(skills_dir), manifest_path=Path(manifest_path)
    )
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")


def _wait_for_server(base_url: str, timeout: float = 15.0) -> None:
    deadline = time.time() + timeout
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            urllib.request.urlopen(f"{base_url}/api/metrics", timeout=1)
            return
        except Exception as exc:  # noqa: BLE001 - polling until the server is up
            last_error = exc
            time.sleep(0.2)
    raise RuntimeError(f"Server did not start in time: {last_error}")


def _write_note(vault_dir, rel_path: str, title: str, body: str) -> None:
    path = vault_dir / rel_path
    path.write_text(f"---\ntitle: {title}\ntags: []\n---\n{body}\n", encoding="utf-8")


@pytest.fixture
def seeded_server(tmp_path):
    vault_dir = tmp_path / "vault"
    for folder in (
        "00-inbox",
        "01-daily",
        "02-projects",
        "03-clients",
        "04-knowledge",
        "05-templates",
        "06-archive",
    ):
        (vault_dir / folder).mkdir(parents=True)
    (vault_dir / "05-templates" / "daily.md").write_text("# {{date}}\n", encoding="utf-8")

    # 3 notes, 2 wikilinks: a -> b -> c (c has no outgoing link).
    _write_note(vault_dir, "04-knowledge/a.md", "Note A", "Links to [[b]].")
    _write_note(vault_dir, "04-knowledge/b.md", "Note B", "Links to [[c]].")
    _write_note(vault_dir, "04-knowledge/c.md", "Note C", "No links.")

    skills_dir = tmp_path / "skills"
    skill_dir = skills_dir / "productivity"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nintent_patterns: []\nkeywords: [task]\npriority: 0\n---\n# Productivity\n",
        encoding="utf-8",
    )

    manifest_path = tmp_path / "skills_manifest.json"
    port = _free_port()

    ctx = multiprocessing.get_context("fork")
    proc = ctx.Process(
        target=_run_server,
        args=(str(vault_dir), str(skills_dir), str(manifest_path), port),
        daemon=True,
    )
    proc.start()

    base_url = f"http://127.0.0.1:{port}"
    try:
        _wait_for_server(base_url)
        yield base_url
    finally:
        proc.terminate()
        proc.join(timeout=5)


def test_dashboard_renders_seeded_metrics(seeded_server):
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=CHROMIUM_PATH, headless=True)
        try:
            page = browser.new_page()
            page.goto(seeded_server)

            page.wait_for_function(
                "document.getElementById('metric-vault-nodes').textContent.includes('Vault Nodes: 3')",
                timeout=10000,
            )

            assert "Graph Links: 2" in page.locator("#metric-graph-links").text_content()
            assert "productivity" in page.locator("#skills-list").text_content()

            # Real (not stubbed) voice status: no voice deps installed in this
            # environment, so both engines correctly report unavailable.
            page.wait_for_function(
                "document.getElementById('voice-stt').textContent.includes('STT: unavailable')",
                timeout=10000,
            )
            assert "TTS: unavailable" in page.locator("#voice-tts").text_content()
            assert "state: idle" in page.locator("#voice-state").text_content()

            # The graph SVG should have rendered 3 circle nodes via D3.
            page.wait_for_function(
                "document.querySelectorAll('#graph-svg circle.graph-node').length === 3",
                timeout=10000,
            )
        finally:
            browser.close()
