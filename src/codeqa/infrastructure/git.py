"""Read pinned local Git snapshots; GitHub operations remain external to codeQA."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import subprocess


class GitReadError(RuntimeError):
    """Local Git snapshot access failed."""


@dataclass(frozen=True, slots=True)
class GitTreeEntry:
    """One verified-path entry from an immutable Git tree enumeration."""

    mode: str
    object_type: str
    object_sha: str
    path: str


class GitReader:
    """Read-only adapter for tracked files, committed blobs and trees."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root).resolve()
        if not self.root.is_dir():
            raise GitReadError("repository root does not exist")

    def _run(self, *args: str) -> bytes:
        try:
            result = subprocess.run(
                ["git", *args], cwd=self.root, capture_output=True, check=False
            )
        except OSError as exc:
            raise GitReadError("git executable unavailable") from exc
        if result.returncode != 0:
            raise GitReadError("cannot read Git snapshot")
        return result.stdout

    def tracked_paths(self) -> list[str]:
        data = self._run("ls-files", "--cached", "-z")
        return [
            part.decode("utf-8", errors="surrogateescape")
            for part in data.split(b"\0") if part
        ]

    def read_file(self, revision: str, path: str) -> bytes:
        if not isinstance(revision, str) or re.fullmatch(r"[0-9a-fA-F]{40}", revision) is None:
            raise GitReadError("revision must be a full Git commit SHA")
        if (
            not isinstance(path, str) or not path or path.startswith("/")
            or "\\" in path or any(p in ("", ".", "..") for p in path.split("/"))
        ):
            raise GitReadError("invalid repository-relative path")
        return self._run("show", f"{revision}:{path}")

    def tree_sha(self, revision: str) -> str:
        """Resolve an exact commit to its tree SHA, never a floating ref."""
        if not isinstance(revision, str) or re.fullmatch(r"[0-9a-fA-F]{40}", revision) is None:
            raise GitReadError("revision must be a full Git commit SHA")
        try:
            tree = self._run("rev-parse", f"{revision}^{{tree}}").decode("ascii").strip()
        except UnicodeDecodeError as exc:
            raise GitReadError("invalid Git tree identity encoding") from exc
        if re.fullmatch(r"[0-9a-f]{40}", tree) is None:
            raise GitReadError("invalid Git tree identity")
        return tree

    def tree_entries(self, revision: str, prefix: str) -> tuple[GitTreeEntry, ...]:
        """Enumerate exact pinned tree paths with strict UTF-8 and blob identities.

        Callers retain responsibility for selecting file types and checking
        source-byte hashes; this method never reads the worktree.
        """
        if not isinstance(revision, str) or re.fullmatch(r"[0-9a-fA-F]{40}", revision) is None:
            raise GitReadError("revision must be a full Git commit SHA")
        if (not isinstance(prefix, str) or not prefix or prefix.startswith("/")
                or "\\" in prefix or any(p in ("", ".", "..") for p in prefix.split("/"))):
            raise GitReadError("invalid Git tree path prefix")
        data = self._run("ls-tree", "-r", "-z", revision, "--", prefix)
        entries: list[GitTreeEntry] = []
        seen: set[str] = set()
        for record in data.split(b"\0"):
            if not record:
                continue
            try:
                metadata, raw_path = record.split(b"\t", 1)
                mode, object_type, object_sha = metadata.decode("ascii").split(" ")
                path = raw_path.decode("utf-8", errors="strict")
            except (ValueError, UnicodeDecodeError) as exc:
                raise GitReadError("malformed pinned Git tree record") from exc
            if (re.fullmatch(r"[0-9]{6}", mode) is None
                    or object_type not in {"blob", "commit", "tree"}
                    or re.fullmatch(r"[0-9a-f]{40}", object_sha) is None
                    or not path.startswith(prefix + "/")
                    or "\\" in path
                    or any(p in ("", ".", "..") for p in path.split("/"))
                    or path in seen):
                raise GitReadError("unsafe or duplicate pinned Git tree entry")
            seen.add(path)
            entries.append(GitTreeEntry(mode, object_type, object_sha, path))
        return tuple(sorted(entries, key=lambda entry: entry.path))
