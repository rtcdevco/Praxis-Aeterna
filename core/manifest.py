"""Skill discovery and manifest generation for the Brain (skill router).

`skills_manifest.json` is a generated artifact, rebuilt on every app startup —
directory scans are cheap at this scale, so "always correct on boot" beats a
cache that can go stale. It is never hand-maintained and is gitignored.
"""

from __future__ import annotations

import json
from pathlib import Path

MANIFEST_VERSION = "1.0.0"

_SCRIPT_SUFFIXES = {".py", ".sh"}


def discover_skills(skills_dir: Path) -> dict[str, dict]:
    """Scan `skills_dir` for skill folders.

    A subdirectory counts as a skill only if it contains a `SKILL.md` file.
    Returns a dict keyed by skill name (the folder name) in sorted order, so
    routing order is deterministic.
    """
    skills: dict[str, dict] = {}
    if not skills_dir.is_dir():
        return skills

    for entry in sorted(skills_dir.iterdir(), key=lambda p: p.name):
        if not entry.is_dir():
            continue
        skill_md = entry / "SKILL.md"
        if not skill_md.is_file():
            continue

        files = sorted(p.name for p in entry.iterdir() if p.is_file())
        has_scripts = any(Path(f).suffix in _SCRIPT_SUFFIXES for f in files)

        skills[entry.name] = {
            "path": str(entry.relative_to(skills_dir.parent)),
            "skill_md": str(skill_md.relative_to(skills_dir.parent)),
            "has_scripts": has_scripts,
            "files": files,
        }

    return skills


def generate_manifest(skills_dir: Path, out_path: Path) -> dict:
    """Build and write the manifest, returning the same dict that was written."""
    manifest = {"skills": discover_skills(skills_dir), "version": MANIFEST_VERSION}
    out_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


