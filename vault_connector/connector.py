"""VaultConnector — the Memory pillar's API between the app and the vault.

The vault is plain Markdown + [[wikilinks]] on disk (Obsidian-compatible), so
there's no database: `scan_vault()` is the index, rebuilt from the filesystem
whenever it goes stale.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from . import wikilinks
from .frontmatter import build_frontmatter, read_note, write_note
from .templates import render_template

TITLE_MATCH_SCORE = 10
TAG_MATCH_SCORE = 5
BODY_MATCH_SCORE = 1
BODY_MATCH_CAP = 5

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slugify(title: str) -> str:
    return _SLUG_RE.sub("-", title.lower()).strip("-") or "untitled"


@dataclass
class NoteRecord:
    path: str  # vault-relative, e.g. "04-knowledge/some-note.md"
    title: str
    tags: list[str]
    content: str  # body only, frontmatter stripped
    mtime: float


@dataclass
class VaultIndex:
    notes: dict[str, NoteRecord] = field(default_factory=dict)

    @property
    def node_count(self) -> int:
        return len(self.notes)


@dataclass
class SearchResult:
    path: str
    title: str
    score: int


class VaultConnector:
    def __init__(self, vault_root: Path):
        self.vault_root = vault_root
        self._index: VaultIndex | None = None
        self._mtimes: dict[str, float] = {}

    def scan_vault(self, force_rescan: bool = False) -> VaultIndex:
        if self._index is not None and not force_rescan and not self._is_stale():
            return self._index

        notes: dict[str, NoteRecord] = {}
        mtimes: dict[str, float] = {}
        for md_path in sorted(self._iter_note_paths()):
            rel = str(md_path.relative_to(self.vault_root))
            post = read_note(md_path)
            mtime = md_path.stat().st_mtime
            notes[rel] = NoteRecord(
                path=rel,
                title=post.metadata.get("title") or md_path.stem,
                tags=list(post.metadata.get("tags") or []),
                content=post.content,
                mtime=mtime,
            )
            mtimes[rel] = mtime

        self._index = VaultIndex(notes=notes)
        self._mtimes = mtimes
        return self._index

    def _iter_note_paths(self):
        # 05-templates holds templates, not notes — they're scaffolding for
        # get_daily_note()/save_note(), not vault content, so they're excluded
        # from the note count / graph rather than permanently inflating both.
        for path in self.vault_root.glob("**/*.md"):
            if "05-templates" in path.relative_to(self.vault_root).parts:
                continue
            yield path

    def _is_stale(self) -> bool:
        current = {
            str(p.relative_to(self.vault_root)): p.stat().st_mtime for p in self._iter_note_paths()
        }
        return current != self._mtimes

    def save_note(
        self,
        content: str,
        folder: str,
        title: str,
        frontmatter_extra: dict | None = None,
    ) -> Path:
        metadata = build_frontmatter(title=title, extra=frontmatter_extra)
        target = self.vault_root / folder / f"{_slugify(title)}.md"
        write_note(target, content, metadata)
        self.scan_vault(force_rescan=True)
        return target

    def search_vault(self, query: str, tags: list[str] | None = None) -> list[SearchResult]:
        index = self.scan_vault()
        query_lower = query.lower()
        tag_filter = {t.lower() for t in tags} if tags else None

        results = []
        for record in index.notes.values():
            if tag_filter and not tag_filter & {t.lower() for t in record.tags}:
                continue

            score = 0
            if query_lower and query_lower in record.title.lower():
                score += TITLE_MATCH_SCORE
            if query_lower and any(query_lower in t.lower() for t in record.tags):
                score += TAG_MATCH_SCORE
            if query_lower:
                body_hits = record.content.lower().count(query_lower)
                score += min(body_hits, BODY_MATCH_CAP) * BODY_MATCH_SCORE

            if score > 0:
                results.append(SearchResult(path=record.path, title=record.title, score=score))

        results.sort(key=lambda r: (-r.score, r.path))
        return results

    def get_graph_data(self) -> dict:
        index = self.scan_vault()
        notes = {path: record.content for path, record in index.notes.items()}
        return wikilinks.build_graph(notes)

    def get_daily_note(self, for_date: date | None = None) -> Path:
        for_date = for_date or date.today()
        target = self.vault_root / "01-daily" / f"{for_date.isoformat()}.md"
        if target.is_file():
            return target

        template_path = self.vault_root / "05-templates" / "daily.md"
        template_text = (
            template_path.read_text(encoding="utf-8") if template_path.is_file() else "# {{date}}\n"
        )
        body = render_template(template_text, date=for_date.isoformat())

        metadata = build_frontmatter(title=for_date.isoformat(), tags=["daily"])
        write_note(target, body, metadata)
        self.scan_vault(force_rescan=True)
        return target
