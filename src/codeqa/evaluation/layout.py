"""Repository-neutral top-level layout evaluation.

No Git, file-system, resource registry, or codeQA directory names in this module.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping, Any


@dataclass(frozen=True)
class LayoutResult:
    missing_directories: tuple[str, ...]
    unexpected_directories: tuple[str, ...]
    missing_files: tuple[str, ...]
    unexpected_files: tuple[str, ...]

    @property
    def passed(self) -> bool:
        return not any((
            self.missing_directories, self.unexpected_directories,
            self.missing_files, self.unexpected_files,
        ))


def _expected_names(policy: Mapping[str, Any], key: str) -> set[str]:
    names = policy.get(key)
    if not isinstance(names, list) or not names:
        raise ValueError(f"{key} must be a nonempty list")
    if any(
        not isinstance(n, str)
        or n in ("", ".", "..")
        or "/" in n or "\\" in n or "\x00" in n
        for n in names
    ):
        raise ValueError(f"{key} contains invalid top-level names")
    if len(names) != len(set(names)):
        raise ValueError(f"{key} contains duplicate names")
    return set(names)


def evaluate_layout(paths: Iterable[str], policy: Mapping[str, Any]) -> LayoutResult:
    """Compare a repository's tracked relative POSIX paths to its own policy."""
    if not isinstance(policy, Mapping):
        raise ValueError("layout policy must be a mapping")
    expected_dirs = _expected_names(policy, "root_directories")
    expected_files = _expected_names(policy, "root_files")
    if expected_dirs & expected_files:
        raise ValueError("directory and file names overlap")

    actual_dirs: set[str] = set()
    actual_files: set[str] = set()
    for path in paths:
        if (
            not isinstance(path, str) or not path
            or path.startswith("/") or "\\" in path
            or any(p in ("", ".", "..") for p in path.split("/"))
        ):
            raise ValueError("invalid repository-relative tracked path")
        first, sep, _ = path.partition("/")
        if sep:
            actual_dirs.add(first)
        else:
            actual_files.add(first)

    return LayoutResult(
        missing_directories=tuple(sorted(expected_dirs - actual_dirs)),
        unexpected_directories=tuple(sorted(actual_dirs - expected_dirs)),
        missing_files=tuple(sorted(expected_files - actual_files)),
        unexpected_files=tuple(sorted(actual_files - expected_files)),
    )
