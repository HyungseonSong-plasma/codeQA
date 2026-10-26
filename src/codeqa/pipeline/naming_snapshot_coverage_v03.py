"""Read-only pinned Git source selection for #91 Python AST coverage.

Pipeline owns Git access + composition; core only computes pure evidence.
"""
from __future__ import annotations

from hashlib import sha1, sha256
from pathlib import Path
import subprocess

from codeqa.core.naming_snapshot_coverage_v03 import (
    NamingSnapshotCoverage, NamingSnapshotCoverageError, _PATH, _SHA,
    scan_selected_python,
)
from codeqa.infrastructure.git import GitReader


def scan_pinned_git(root: Path, *, revision: str) -> NamingSnapshotCoverage:
    """Read the exact committed tree and verify every Git blob before scanning.

    Uses only git ls-tree/show locally. Never executes imported repository code,
    never traverses the working tree, and never trusts a caller's file list.
    """
    if not isinstance(revision, str) or not _SHA.fullmatch(revision):
        raise NamingSnapshotCoverageError("full lower-case commit SHA required")
    reader = GitReader(root)
    try:
        result = subprocess.run(
            ["git", "ls-tree", "-rz", revision, "--", "src/codeqa"],
            cwd=reader.root, capture_output=True, check=False,
        )
    except OSError as exc:
        raise NamingSnapshotCoverageError("git unavailable") from exc
    if result.returncode != 0:
        raise NamingSnapshotCoverageError("cannot independently read pinned tree")
    sources: dict[str, bytes] = {}
    digests: dict[str, str] = {}
    for record in result.stdout.split(b"\0"):
        if not record:
            continue
        try:
            metadata, path_raw = record.split(b"\t", 1)
            mode, object_type, blob_raw = metadata.split(b" ", 2)
            path = path_raw.decode("utf-8", errors="strict")
            blob = blob_raw.decode("ascii", errors="strict")
        except (ValueError, UnicodeDecodeError) as exc:
            raise NamingSnapshotCoverageError("malformed tracked Git tree record") from exc
        if not path.endswith(".py"):
            continue
        if (mode not in {b"100644", b"100755"} or object_type != b"blob"
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
