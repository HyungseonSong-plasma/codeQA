"""Resolve codeQA resources by logical ID rather than by consumer-owned paths.

The only fixed bootstrap location is the repository-root pyproject.toml.
Resource locations are repository-relative and cannot escape the checkout.
"""
from __future__ import annotations

import json
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import tomllib
from typing import Any


_RESOURCE_ID = re.compile(r"[a-z][a-z0-9_]*\Z")


class ResourceResolutionError(ValueError):
    """A resource cannot be safely and unambiguously resolved or loaded."""


def validate_resource_path(relative: str, resource_id: str) -> PurePosixPath:
    """Validate a registry location independently of its storage mechanism."""
    if not isinstance(relative, str) or not relative.strip():
        raise ResourceResolutionError(f"invalid path for resource: {resource_id}")
    path = PurePosixPath(relative)
    if (
        path.is_absolute()
        or PureWindowsPath(relative).is_absolute()
        or "\\" in relative
        or any(part in {"", ".", ".."} for part in relative.split("/"))
    ):
        raise ResourceResolutionError(f"unsafe path for resource: {resource_id}")
    return path


def registry_path(config: dict[str, Any], resource_id: str) -> PurePosixPath:
    """Obtain the validated location from an in-memory TOML mapping."""
    if not isinstance(resource_id, str) or not _RESOURCE_ID.fullmatch(resource_id):
        raise ResourceResolutionError("invalid resource ID")
    table: Any = config
    for key in ("tool", "codeqa", "resources"):
        if not isinstance(table, dict) or key not in table:
            raise ResourceResolutionError("missing [tool.codeqa.resources] registry")
        table = table[key]
    if not isinstance(table, dict):
        raise ResourceResolutionError("resource registry must be a TOML table")
    if resource_id not in table:
        raise ResourceResolutionError(f"unregistered resource ID: {resource_id}")
    return validate_resource_path(table[resource_id], resource_id)


def parse_registry(content: bytes) -> dict[str, Any]:
    """Parse a TOML registry from working-tree or historical Git bytes."""
    try:
        return tomllib.loads(content.decode("utf-8"))
    except (UnicodeError, tomllib.TOMLDecodeError) as exc:
        raise ResourceResolutionError("invalid resource registry TOML") from exc


def parse_json(content: bytes, resource_id: str) -> Any:
    """Parse registered JSON identically for historical and current resources."""
    try:
        return json.loads(content.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ResourceResolutionError(f"invalid JSON resource: {resource_id}") from exc


class ResourceRegistry:
    """Resolve configured resource IDs against one explicit repository root."""

    def __init__(self, repository_root: Path) -> None:
        self.root = Path(repository_root).resolve()
        if not self.root.is_dir():
            raise ResourceResolutionError("repository root does not exist")

    def _config(self) -> dict[str, Any]:
        try:
            return parse_registry((self.root / "pyproject.toml").read_bytes())
        except OSError as exc:
            raise ResourceResolutionError("cannot load repository resource registry") from exc

    def resolve(self, resource_id: str) -> Path:
        """Return the verified in-repository file path for a logical resource ID."""
        relative = registry_path(self._config(), resource_id)
        candidate = (self.root / Path(*relative.parts)).resolve()
        if not candidate.is_relative_to(self.root):
            raise ResourceResolutionError(f"resource escapes repository: {resource_id}")
        if not candidate.is_file():
            raise ResourceResolutionError(f"resource file missing: {resource_id}")
        return candidate

    def load_json(self, resource_id: str) -> Any:
        """Load a JSON resource; parsing errors fail closed."""
        try:
            return parse_json(self.resolve(resource_id).read_bytes(), resource_id)
        except OSError as exc:
            raise ResourceResolutionError(f"cannot read resource: {resource_id}") from exc
