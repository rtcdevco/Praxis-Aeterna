from vault_connector.wikilinks import build_backlinks, build_graph, find_wikilinks, resolve_target


def test_find_wikilinks_plain():
    assert find_wikilinks("See [[Project Alpha]] for details.") == [("Project Alpha", None)]


def test_find_wikilinks_aliased():
    assert find_wikilinks("See [[Project Alpha|the alpha project]].") == [
        ("Project Alpha", "the alpha project")
    ]


def test_find_wikilinks_anchored():
    assert find_wikilinks("See [[Project Alpha#Status]].") == [("Project Alpha", None)]


def test_find_wikilinks_multiple():
    text = "Links: [[A]], [[B|alias]], and [[C#heading]]."
    assert find_wikilinks(text) == [("A", None), ("B", "alias"), ("C", None)]


def test_resolve_target_unique_stem():
    paths = ["02-projects/Alpha.md", "04-knowledge/Beta.md"]
    assert resolve_target("Alpha", paths) == "02-projects/Alpha.md"


def test_resolve_target_no_match_returns_none():
    assert resolve_target("Nonexistent", ["02-projects/Alpha.md"]) is None


def test_resolve_target_exact_path_wins():
    paths = ["02-projects/Alpha.md", "03-clients/Alpha.md"]
    # Path-like target should resolve to the exact match.
    assert resolve_target("02-projects/Alpha", paths) == "02-projects/Alpha.md"


def test_resolve_target_ambiguous_stem_picks_first_alphabetical():
    paths = ["03-clients/Alpha.md", "02-projects/Alpha.md"]
    assert resolve_target("Alpha", paths) == "02-projects/Alpha.md"


def test_build_graph_produces_nodes_and_edges():
    notes = {
        "02-projects/Alpha.md": "Related to [[Beta]].",
        "04-knowledge/Beta.md": "No links here.",
    }
    graph = build_graph(notes)

    assert {n["id"] for n in graph["nodes"]} == set(notes)
    assert graph["edges"] == [{"source": "02-projects/Alpha.md", "target": "04-knowledge/Beta.md"}]


def test_build_graph_ignores_self_links_and_dangling_links():
    notes = {
        "a.md": "Links to [[a]] (self) and [[nonexistent]].",
    }
    graph = build_graph(notes)
    assert graph["edges"] == []


def test_build_graph_dedupes_repeated_links():
    notes = {
        "a.md": "[[b]] and [[b]] again.",
        "b.md": "",
    }
    graph = build_graph(notes)
    assert graph["edges"] == [{"source": "a.md", "target": "b.md"}]


def test_build_backlinks_transposes_edges():
    graph = {
        "nodes": [],
        "edges": [
            {"source": "a.md", "target": "c.md"},
            {"source": "b.md", "target": "c.md"},
        ],
    }
    backlinks = build_backlinks(graph)
    assert backlinks == {"c.md": ["a.md", "b.md"]}
