"""[[wikilink]] parsing and backlink graph construction for the Memory pillar."""

from __future__ import annotations

import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

# Captures the link target (group 1, dropping any #heading anchor) and an
# optional |Alias display text (group 2).
WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]+)?(?:\|([^\]]+))?\]\]")


def find_wikilinks(text: str) -> list[tuple[str, str | None]]:
    """Return (target, alias) pairs for every [[wikilink]] in `text`."""
    links = []
    for match in WIKILINK_RE.finditer(text):
        target = match.group(1).strip()
        alias = match.group(2).strip() if match.group(2) else None
        links.append((target, alias))
    return links


def resolve_target(target: str, note_paths: list[str]) -> str | None:
    """Resolve a wikilink target to one of `note_paths` (vault-relative, with .md).

    Known, documented limitation: if a target's filename stem exists in more
    than one folder, the exact-path match wins when the link itself looks
    path-like; otherwise the first alphabetical match wins and a warning is
    logged. This is a deterministic, tested tradeoff — not silent
    nondeterminism.
    """
    target_no_suffix = target[:-3] if target.endswith(".md") else target

    exact = [p for p in note_paths if p == target or p[: -len(".md")] == target_no_suffix]
    if exact:
        return sorted(exact)[0]

    stem = Path(target_no_suffix).name
    by_stem = [p for p in note_paths if Path(p).stem == stem]
    if not by_stem:
        return None
    if len(by_stem) > 1:
        logger.warning(
            "Ambiguous wikilink target %r resolves to %d notes (%s); picking %s",
            target,
            len(by_stem),
            ", ".join(sorted(by_stem)),
            sorted(by_stem)[0],
        )
    return sorted(by_stem)[0]


def build_graph(notes: dict[str, str]) -> dict:
    """Build a nodes+edges graph from vault-relative-path -> markdown-body content.

    Edges are deduped resolved forward links; a link to a note that doesn't
    exist simply produces no edge (no "dangling node" placeholders).
    """
    note_paths = list(notes)
    nodes = [{"id": path, "label": Path(path).stem} for path in sorted(note_paths)]

    edges = []
    seen: set[tuple[str, str]] = set()
    for path, content in notes.items():
        for target, _alias in find_wikilinks(content):
            resolved = resolve_target(target, note_paths)
            if resolved is None or resolved == path:
                continue
            key = (path, resolved)
            if key in seen:
                continue
            seen.add(key)
            edges.append({"source": path, "target": resolved})

    return {"nodes": nodes, "edges": edges}


def build_backlinks(graph: dict) -> dict[str, list[str]]:
    """Transpose a graph's edges into a target -> [sources] backlink map."""
    backlinks: dict[str, list[str]] = {}
    for edge in graph["edges"]:
        backlinks.setdefault(edge["target"], []).append(edge["source"])
    for sources in backlinks.values():
        sources.sort()
    return backlinks
