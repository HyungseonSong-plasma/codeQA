"""Trusted caller-owned persistent *file-local* Python CCG cache (#101).

It NEVER stores ASTs, full CCG graphs, QA verdicts, source selection,
cross-file bindings, static-impact decisions, tool receipts or formal proofs.
All those are recomputed per snapshot by the existing Python pipeline.
Only POSIX-style, trusted local cache directories are supported.
"""
from __future__ import annotations

from collections.abc import Mapping
from contextlib import contextmanager
from hashlib import sha256
import json
import os
from pathlib import Path
import platform
import re
import sys
import tempfile
from typing import Any, Iterator

try:
    import fcntl
except ImportError:  # pragma: no cover - portability boundary
    fcntl = None

from .python_snapshot import PythonAnalysisCache


class PersistentCacheError(ValueError):
    """The configured cache store or its trust boundary is not usable."""


def _dump(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def _safe_source(path: str) -> bool:
    return bool(
        isinstance(path, str)
        and re.fullmatch(r"[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*", path)
        and all(p not in (".", "..") for p in path.split("/"))
    )


def _producer() -> str:
    # Extraction uses _Extract and ModuleBindings; these two files and the
    # parser Python version define the file-local semantic producer.
    root = Path(__file__).resolve().parent
    parts = [b"codeqa-ccg-file-extract-cache-v0.1",
             sys.implementation.cache_tag.encode(),
             platform.python_version().encode()]
    parts.extend((root / filename).read_bytes()
                 for filename in ("python.py", "lexical.py", "python_snapshot.py"))
    return sha256(b"\0".join(parts)).hexdigest()


class PythonPersistentExtractionCache:
    """Atomic JSON record store with explicit namespace and per-file digests.

    Root must be a caller-owned TRUSTED directory; hashes detect accidental
    corruption, not a malicious local writer who can replace both data/hash.
    Locking is exclusive POSIX flock; on unsupported systems fail closed.
    """

    def __init__(
        self, root: Path, *, namespace: str,
        max_entries: int = 512, max_blob_bytes: int = 4_000_000,
    ) -> None:
        if fcntl is None:
            raise PersistentCacheError("POSIX file locking unavailable")
        if (not isinstance(namespace, str) or not namespace.strip()
                or "\x00" in namespace or len(namespace) > 256):
            raise PersistentCacheError("explicit trusted cache namespace required")
        if (type(max_entries) is not int or max_entries < 1
                or type(max_blob_bytes) is not int or max_blob_bytes < 1024):
            raise PersistentCacheError("invalid cache capacity")
        self.root = Path(root)
        self.namespace = namespace
        self.max_entries = max_entries
        self.max_blob_bytes = max_blob_bytes
        self.producer = _producer()
        self.root.mkdir(parents=True, exist_ok=True)
        if not self.root.is_dir() or self.root.is_symlink():
            raise PersistentCacheError("cache root must be a trusted real directory")

    @contextmanager
    def _lock(self) -> Iterator[None]:
        descriptor = os.open(self.root / ".lock", os.O_CREAT | os.O_RDWR, 0o600)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            yield
        finally:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)

    def _file(self, path: str, source_sha: str) -> Path:
        if not _safe_source(path) or not re.fullmatch("[a-f0-9]{64}", source_sha):
            raise PersistentCacheError("invalid source/cache identity")
        key = sha256(_dump([
            "0.1", self.namespace, self.producer, path, source_sha
        ])).hexdigest()
        return self.root / (key + ".json")

    def _load(self, filename: Path, path: str, digest: str):
        try:
            if filename.is_symlink() or filename.stat().st_size > self.max_blob_bytes:
                return None
            record = json.loads(filename.read_bytes())
            if not isinstance(record, dict) or set(record) != {"payload", "sha256"}:
                return None
            payload = record["payload"]
            if (not isinstance(payload, dict) or
                not isinstance(record["sha256"], str) or
                sha256(_dump(payload)).hexdigest() != record["sha256"] or
                payload.get("version") != "0.1" or
                payload.get("namespace") != self.namespace or
                payload.get("producer") != self.producer or
                payload.get("path") != path or
                payload.get("source_sha256") != digest):
                return None
            nodes, edges = payload.get("nodes"), payload.get("edges")
            if (not isinstance(nodes, list) or not isinstance(edges, list)
                    or not nodes or
                    not all(isinstance(item, dict) and
                            all(k in item for k in ("id", "kind", "name", "provenance"))
                            for item in nodes)
                    or not all(isinstance(item, dict) and
                               all(k in item for k in
                                   ("source", "kind", "resolution", "provenance"))
                               for item in edges)):
                return None
            return tuple(nodes), tuple(edges)
        except (OSError, ValueError, UnicodeError, TypeError, KeyError):
            return None

    def hydrate(self, cache: PythonAnalysisCache, sources: Mapping[str, str]) -> int:
        """Load exact-source file-local facts; no analysis results or ASTs."""
        if not isinstance(cache, PythonAnalysisCache):
            raise TypeError("expected caller-owned PythonAnalysisCache")
        reused = 0
        with self._lock():
            for path in sorted(sources):
                text = sources[path]
                if not path.endswith(".py") or not isinstance(text, str):
                    continue
                digest = sha256(text.encode("utf-8")).hexdigest()
                filename = self._file(path, digest)
                result = self._load(filename, path, digest)
                if result is None:
                    continue  # Corrupt/missing/stale: recompute locally.
                cache.graph_facts[(path, digest)] = result
                cache.graph_facts.move_to_end((path, digest))
                if len(cache.graph_facts) > cache.max_entries:
                    cache.graph_facts.popitem(last=False)
                os.utime(filename, None)
                reused += 1
        return reused

    def save(self, cache: PythonAnalysisCache) -> int:
        """Atomically write bounded immutable extraction facts; prune LRU."""
        if not isinstance(cache, PythonAnalysisCache):
            raise TypeError("expected caller-owned PythonAnalysisCache")
        written = 0
        with self._lock():
            for (path, digest), (nodes, edges) in cache.graph_facts.items():
                filename = self._file(path, digest)
                payload = {
                    "version": "0.1", "namespace": self.namespace,
                    "producer": self.producer,
                    "path": path, "source_sha256": digest,
                    "nodes": list(nodes), "edges": list(edges),
                }
                record = {"payload": payload, "sha256": sha256(_dump(payload)).hexdigest()}
                blob = _dump(record)
                if len(blob) > self.max_blob_bytes:
                    continue  # large file means future cold extraction, never bad data
                if filename.exists() and self._load(filename, path, digest) is not None:
                    continue
                temporary: str | None = None
                try:
                    with tempfile.NamedTemporaryFile(
                        mode="wb", prefix=".codeqa-", suffix=".tmp",
                        dir=self.root, delete=False,
                    ) as out:
                        temporary = out.name
                        out.write(blob)
                        out.flush()
                        os.fsync(out.fileno())
                    os.replace(temporary, filename)
                    written += 1
                finally:
                    if temporary is not None:
                        try:
                            Path(temporary).unlink(missing_ok=True)
                        except OSError:
                            pass
            candidates = sorted(
                (item for item in self.root.glob("*.json") if
                 item.is_file() and not item.is_symlink()),
                key=lambda item: (item.stat().st_mtime_ns, item.name),
            )
            for outdated in candidates[:-self.max_entries]:
                try:
                    outdated.unlink(missing_ok=True)
                except OSError:
                    pass
        return written
