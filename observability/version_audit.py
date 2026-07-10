# version: 1
# changed: 2026-07-09 | Claude | initial implementation
"""File-level version/change audit trail.

Scoped to `observability/` in this PR only, per the constraint not to modify
existing brain/memory/face/voice/handoff logic — those modules don't carry a
`# version: N` header and this module doesn't retrofit one onto them. It's a
general-purpose utility (works on any file with the header convention below),
just applied narrowly here.

Convention: any audited file starts with two comment lines:
    # version: <int>
    # changed: <ISO date> | <author> | <one-line description>
"""

from __future__ import annotations

import hashlib
import re
import time
from contextlib import closing
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS file_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    path TEXT NOT NULL,
    version INTEGER NOT NULL,
    content_hash TEXT NOT NULL,
    author TEXT NOT NULL,
    ts REAL NOT NULL,
    description TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_file_versions_path ON file_versions(path);
"""

_VERSION_RE = re.compile(r"^#\s*version:\s*(\d+)\s*$", re.MULTILINE)
_CHANGED_RE = re.compile(r"^#\s*changed:\s*(.+)$", re.MULTILINE)


def compute_file_hash(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_version_header(path: str | Path) -> tuple[int | None, str | None]:
    """Returns (version, changed_line) parsed from a file's header, or (None, None)
    if the file doesn't have the `# version: N` convention.
    """
    text = Path(path).read_text(encoding="utf-8")
    version_match = _VERSION_RE.search(text)
    changed_match = _CHANGED_RE.search(text)
    version = int(version_match.group(1)) if version_match else None
    changed = changed_match.group(1).strip() if changed_match else None
    return version, changed


class VersionAuditLog:
    def __init__(self, conn):
        self._conn = conn
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def record_change(self, path: str | Path, author: str, description: str) -> int:
        """Record the current on-disk version/hash of `path`. Raises if the file
        has no `# version: N` header — callers must opt into the convention
        explicitly, not have one silently assumed.
        """
        version, _changed = read_version_header(path)
        if version is None:
            raise ValueError(f"{path} has no '# version: N' header — cannot audit it")

        content_hash = compute_file_hash(path)
        with closing(self._conn.cursor()) as cur:
            cur.execute(
                "INSERT INTO file_versions (path, version, content_hash, author, ts, description) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (str(path), version, content_hash, author, time.time(), description),
            )
        self._conn.commit()
        return version

    def check_version_bumped(self, path: str | Path) -> bool:
        """True if `path`'s current on-disk content hash differs from its last
        recorded hash AND its version header increased — the actual enforcement
        check: a content change without a version bump fails this.
        """
        with closing(self._conn.cursor()) as cur:
            cur.execute(
                "SELECT version, content_hash FROM file_versions WHERE path = ? "
                "ORDER BY ts DESC LIMIT 1",
                (str(path),),
            )
            row = cur.fetchone()

        current_version, _ = read_version_header(path)
        current_hash = compute_file_hash(path)

        if row is None:
            return True  # never recorded — nothing to compare against yet

        last_version, last_hash = row
        if current_hash == last_hash:
            return True  # unchanged — no bump required
        return current_version is not None and current_version > last_version

    def log(self, limit: int = 10) -> list[dict]:
        with closing(self._conn.cursor()) as cur:
            cur.execute(
                "SELECT path, version, content_hash, author, ts, description "
                "FROM file_versions ORDER BY ts DESC LIMIT ?",
                (limit,),
            )
            return [
                {
                    "path": r[0], "version": r[1], "content_hash": r[2],
                    "author": r[3], "ts": r[4], "description": r[5],
                }
                for r in cur.fetchall()
            ]
