"""SkillRouter — the Brain's regex-first, keyword-fallback intent router.

Routing is two-phase and fully deterministic (pure `re` + string ops, no I/O
per call, no LLM in the loop):

1. Regex phase: each skill's `SKILL.md` frontmatter declares `intent_patterns`
   (a list of regex strings). Patterns are tried in manifest order (which is
   alphabetical by skill name — see `core/manifest.py`); the first match wins.
2. Keyword fallback: if nothing matches, frontmatter `keywords` are scored by
   normalized overlap against the tokenized utterance. The highest score above
   a floor wins; ties are broken by `priority` (higher wins) then by manifest
   order (i.e. alphabetically), because we only replace the current best on a
   strict improvement.

If neither phase produces a match, `route()` returns `None` — the caller
should surface "no skill matched" rather than silently guessing.
"""

from __future__ import annotations

import re
from pathlib import Path

import frontmatter

KEYWORD_MATCH_FLOOR = 0.15

_TOKEN_RE = re.compile(r"[a-z0-9']+")
_CONTEXT_FILES_HEADING_RE = re.compile(r"^## Context Files\s*$", re.MULTILINE)
_NEXT_HEADING_RE = re.compile(r"^## ", re.MULTILINE)
_CONTEXT_FILE_BULLET_RE = re.compile(r"^-\s+([^\s—]+)\s+—", re.MULTILINE)


def _tokenize(text: str) -> set[str]:
    return set(_TOKEN_RE.findall(text.lower()))


def parse_context_files(skill_md_text: str) -> list[str]:
    """Extract declared filenames from a SKILL.md's '## Context Files' section.

    Expects bullets shaped like `- filename.md — description`. Returns an
    empty list if the section is missing or has no matching bullets.
    """
    heading = _CONTEXT_FILES_HEADING_RE.search(skill_md_text)
    if not heading:
        return []

    section_start = heading.end()
    next_heading = _NEXT_HEADING_RE.search(skill_md_text, section_start)
    section_end = next_heading.start() if next_heading else len(skill_md_text)

    section_text = skill_md_text[section_start:section_end]
    return _CONTEXT_FILE_BULLET_RE.findall(section_text)


class SkillRouter:
    def __init__(self, manifest: dict, repo_root: Path):
        self._repo_root = repo_root
        self._order: list[str] = list(manifest["skills"].keys())
        self._skill_md_path: dict[str, Path] = {}
        self._compiled: dict[str, dict] = {}

        for name, meta in manifest["skills"].items():
            skill_md_path = repo_root / meta["skill_md"]
            self._skill_md_path[name] = skill_md_path
            post = frontmatter.load(skill_md_path)

            patterns = [re.compile(p, re.IGNORECASE) for p in post.metadata.get("intent_patterns", [])]
            keywords = {k.lower() for k in post.metadata.get("keywords", [])}
            priority = int(post.metadata.get("priority", 0))

            self._compiled[name] = {
                "patterns": patterns,
                "keywords": keywords,
                "priority": priority,
            }

    @property
    def skill_names(self) -> list[str]:
        return list(self._order)

    def skill_md_path(self, name: str) -> Path:
        return self._skill_md_path[name]

    def route(self, utterance: str) -> str | None:
        for name in self._order:
            for pattern in self._compiled[name]["patterns"]:
                if pattern.search(utterance):
                    return name

        tokens = _tokenize(utterance)
        best_name: str | None = None
        best_key: tuple[float, int] | None = None

        for name in self._order:
            keywords = self._compiled[name]["keywords"]
            if not keywords:
                continue
            score = len(tokens & keywords) / len(keywords)
            if score < KEYWORD_MATCH_FLOOR:
                continue
            key = (score, self._compiled[name]["priority"])
            if best_key is None or key > best_key:
                best_name, best_key = name, key

        return best_name
