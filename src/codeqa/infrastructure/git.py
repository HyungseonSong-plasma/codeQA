"""Read pinned local Git snapshots; GitHub operations remain external to codeQA."""
from __future__ import annotations

from pathlib import Path
import re
import subprocess


class GitReadError(RuntimeError):
    """Local Git snapshot access failed."""


class GitReader:
    """Read-only adapter for tracked files and committed blobs."""

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
