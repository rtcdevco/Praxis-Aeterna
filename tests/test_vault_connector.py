from datetime import date

from vault_connector.connector import VaultConnector


def _write_note(vault_root, rel_path, title, tags, body):
    path = vault_root / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    tags_yaml = "[" + ", ".join(tags) + "]"
    path.write_text(
        f"---\ntitle: {title}\ntags: {tags_yaml}\n---\n{body}\n",
        encoding="utf-8",
    )


def test_scan_vault_empty(tmp_path):
    connector = VaultConnector(tmp_path)
    index = connector.scan_vault()
    assert index.node_count == 0


def test_scan_vault_reads_frontmatter(tmp_path):
    _write_note(tmp_path, "04-knowledge/alpha.md", "Alpha Note", ["research"], "Some body text.")
    connector = VaultConnector(tmp_path)
    index = connector.scan_vault()

    assert index.node_count == 1
    record = index.notes["04-knowledge/alpha.md"]
    assert record.title == "Alpha Note"
    assert record.tags == ["research"]
    assert "Some body text." in record.content


def test_save_note_writes_frontmatter_and_is_findable(tmp_path):
    connector = VaultConnector(tmp_path)
    path = connector.save_note("Body content here.", "04-knowledge", "My New Finding")

    assert path.is_file()
    assert path.name == "my-new-finding.md"

    index = connector.scan_vault()
    rel = str(path.relative_to(tmp_path))
    assert rel in index.notes
    assert index.notes[rel].title == "My New Finding"


def test_search_vault_scores_title_over_tag_over_body(tmp_path):
    _write_note(tmp_path, "a.md", "Widgets Overview", [], "unrelated body")
    _write_note(tmp_path, "b.md", "Something Else", ["widgets"], "unrelated body")
    _write_note(tmp_path, "c.md", "Another Note", [], "this note mentions widgets in passing")

    connector = VaultConnector(tmp_path)
    results = connector.search_vault("widgets")

    assert [r.path for r in results] == ["a.md", "b.md", "c.md"]
    assert results[0].score > results[1].score > results[2].score


def test_search_vault_tag_filter(tmp_path):
    _write_note(tmp_path, "a.md", "Note A", ["research"], "body")
    _write_note(tmp_path, "b.md", "Note B", ["productivity"], "body")

    connector = VaultConnector(tmp_path)
    results = connector.search_vault("Note", tags=["research"])

    assert [r.path for r in results] == ["a.md"]


def test_get_daily_note_creates_from_template(tmp_path):
    (tmp_path / "05-templates").mkdir(parents=True)
    (tmp_path / "05-templates" / "daily.md").write_text("# {{date}}\n\n## Focus\n", encoding="utf-8")

    connector = VaultConnector(tmp_path)
    target_date = date(2026, 1, 15)
    path = connector.get_daily_note(target_date)

    assert path.is_file()
    assert path.name == "2026-01-15.md"
    assert "# 2026-01-15" in path.read_text(encoding="utf-8")


def test_get_daily_note_returns_existing_without_overwriting(tmp_path):
    (tmp_path / "05-templates").mkdir(parents=True)
    (tmp_path / "05-templates" / "daily.md").write_text("# {{date}}\n", encoding="utf-8")

    connector = VaultConnector(tmp_path)
    target_date = date(2026, 1, 15)
    first = connector.get_daily_note(target_date)
    first.write_text(first.read_text(encoding="utf-8") + "\nManually added line.\n", encoding="utf-8")

    second = connector.get_daily_note(target_date)

    assert second == first
    assert "Manually added line." in second.read_text(encoding="utf-8")


def test_get_graph_data_reflects_wikilinks(tmp_path):
    # Wikilinks reference a note's filename stem (Obsidian convention), not its
    # frontmatter title — so the link target here is "b", matching b.md.
    _write_note(tmp_path, "a.md", "Note A", [], "Links to [[b]].")
    _write_note(tmp_path, "b.md", "Note B", [], "No links.")

    connector = VaultConnector(tmp_path)
    graph = connector.get_graph_data()

    assert len(graph["nodes"]) == 2
    assert graph["edges"] == [{"source": "a.md", "target": "b.md"}]
