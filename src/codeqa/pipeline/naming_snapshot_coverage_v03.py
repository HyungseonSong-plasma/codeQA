"""Read-only pinned Git source selection for #91 Python AST coverage.

Infrastructure owns Git subprocess access; pipeline composes pinned evidence.
"""
from __future__ import annotations

from hashlib import sha1, sha256
from pathlib import Path

from codeqa.core.naming_snapshot_coverage_v03 import (
    NamingSnapshotCoverage, NamingSnapshotCoverageError, _PATH, _SHA,
    scan_selected_python,
)
from codeqa.infrastructure.git import GitReadError, GitReader


def scan_pinned_git(root: Path, *, revision: str) -> NamingSnapshotCoverage:
    """Read the exact committed tree and verify every Git blob before scanning.

    Uses only git ls-tree/show locally. Never executes imported repository code,
    never traverses the working tree, and never trusts a caller's file list.
    """
    if not isinstance(revision, str) or not _SHA.fullmatch(revision):
        raise NamingSnapshotCoverageError("full lower-case commit SHA required")
    reader = GitReader(root)
    try:
        entries = reader.tree_entries(revision, "src/codeqa")
    except GitReadError as exc:
        raise NamingSnapshotCoverageError("cannot independently read pinned tree") from exc
    sources: dict[str, bytes] = {}
    digests: dict[str, str] = {}
    for entry in entries:
        path = entry.path
        blob = entry.object_sha
        if not path.endswith(".py"):
            continue
        if (entry.mode not in {"100644", "100755"}
                or entry.object_type != "blob"
                or not _PATH.fullmatch(path)
                or any(c in {".", ".."} or c.endswith((".", " "))
                       for c in path.split("/"))
                or not _SHA.fullmatch(blob)
                or path in sources):
            raise NamingSnapshotCoverageError("unsafe, ambiguous or untracked Python Git entry")
        body = reader.read_file(revision, path)
        if sha1(b"blob " + str(len(body)).encode() + b"\0" + body).hexdigest() != blob:
            raise NamingSnapshotCoverageError("Git tree/blob source mismatch")
        sources[path] = body
        digests[path] = sha256(body).hexdigest()
    if not sources:
        raise NamingSnapshotCoverageError("empty pinned Python repository selection")
    return scan_selected_python(revision=revision, sources=sources, expected_digests=digests)
