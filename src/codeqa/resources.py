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


class ResourceRegistry:
    """Resolve configured resource IDs against one explicit repository root."""

    def __init__(self, repository_root: Path) -> None:
        self.root = Path(repository_root).resolve()
        if not self.root.is_dir():
            raise ResourceResolutionError("repository root does not exist")

    def _resources(self) -> dict[str, str]:
        config_path = self.root / "pyproject.toml"
        try:
            with config_path.open("rb") as stream:
                config = tomllib.load(stream)
        except (OSError, tomllib.TOMLDecodeError) as exc:
            raise ResourceResolutionError("cannot load repository resource registry") from exc

        table: Any = config
        for key in ("tool", "codeqa", "resources"):
            if not isinstance(table, dict) or key not in table:
                raise ResourceResolutionError("missing [tool.codeqa.resources] registry")
            table = table[key]
        if not isinstance(table, dict):
            raise ResourceResolutionError("resource registry must be a TOML table")
        return table

    def resolve(self, resource_id: str) -> Path:
        """Return the verified in-repository file path for a logical resource ID."""
        if not isinstance(resource_id, str) or not _RESOURCE_ID.fullmatch(resource_id):
            raise ResourceResolutionError("invalid resource ID")

        resources = self._resources()
        if resource_id not in resources:
            raise ResourceResolutionError(f"unregistered resource ID: {resource_id}")

        relative = resources[resource_id]
        if not isinstance(relative, str) or not relative.strip():
            raise ResourceResolutionError(f"invalid path for resource: {resource_id}")
        # Registry paths have one cross-platform canonical representation.
        path = PurePosixPath(relative)
        if (
            path.is_absolute()
            or PureWindowsPath(relative).is_absolute()
            or "\\" in relative
            or any(part in {"", ".", ".."} for part in relative.split("/"))
        ):
            raise ResourceResolutionError(f"unsafe path for resource: {resource_id}")

        candidate = (self.root / Path(*path.parts)).resolve()
        if not candidate.is_relative_to(self.root):
            raise ResourceResolutionError(f"resource escapes repository: {resource_id}")
        if not candidate.is_file():
            raise ResourceResolutionError(f"resource file missing: {resource_id}")
        return candidate

    def load_json(self, resource_id: str) -> Any:
        """Load a JSON resource; parsing errors fail closed."""
        resource = self.resolve(resource_id)
        try:
            with resource.open("r", encoding="utf-8") as stream:
                return json.load(stream)
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise ResourceResolutionError(f"invalid JSON resource: {resource_id}") from exc
