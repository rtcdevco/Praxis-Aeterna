"""Thin wrapper over `python-frontmatter` for reading/writing vault notes.

Using a real YAML-frontmatter library instead of hand-rolled regex parsing
avoids the classic footguns around multiline values and lists in frontmatter
blocks.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import frontmatter as fm


def read_note(path: Path) -> fm.Post:
    return fm.load(path)


def write_note(path: Path, content: str, metadata: dict) -> None:
    post = fm.Post(content, **metadata)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(fm.dumps(post) + "\n", encoding="utf-8")


def build_frontmatter(title: str, tags: list[str] | None = None, extra: dict | None = None) -> dict:
    metadata: dict = {
        "title": title,
        "created": date.today().isoformat(),
        "tags": tags or [],
    }
    if extra:
        metadata.update(extra)
    return metadata
