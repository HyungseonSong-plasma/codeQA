"""Strict opt-in validation of a separately shipped codeQA resource bundle.

Does not auto-discover resources, execute code, or certify production SDK/DB
compatibility. A caller must independently pin package version and source SHA.
"""
from __future__ import annotations

from hashlib import sha256
import json
import math
from pathlib import Path
import re
import stat
import tomllib
import unicodedata
from typing import Any
from zipfile import BadZipFile, ZipFile


class ResourceBundleError(ValueError):
    """A bundle cannot be trusted as the selected package resource snapshot."""


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ResourceBundleError("duplicate JSON manifest key")
        result[key] = value
    return result


def _reject_nonfinite_json(value: str) -> Any:
    raise ResourceBundleError("non-finite registered JSON resource value")


def _finite_json_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ResourceBundleError("non-finite registered JSON resource value")
    return parsed


_WINDOWS_DEVICE_NAMES = {"CON", "PRN", "AUX", "NUL"} | {
    f"{prefix}{n}" for prefix in ("COM", "LPT") for n in range(1, 10)
}


def _safe_path(value: Any) -> bool:
    if (not isinstance(value, str) or not value or value.startswith("/")
            or "\\" in value or any(ord(c) < 32 or ord(c) == 127 for c in value)):
        return False
    for part in value.split("/"):
        if (part in ("", ".", "..") or ":" in part or part.endswith((".", " "))
                or unicodedata.normalize("NFC", part) != part
                or part.split(".", 1)[0].upper() in _WINDOWS_DEVICE_NAMES):
            return False
    return True


def _portable_path_key(value: str) -> str:
    """Detect archive entries that alias on case-insensitive filesystems."""
    return unicodedata.normalize("NFC", value).casefold()


def unpack_verified_resource_bundle(
    bundle: Path, destination: Path, *, version: str, source_revision: str,
) -> dict[str, Any]:
    """Verify *all* bytes and registry mappings before extracting any file."""
    if not isinstance(version, str) or not version or not re.fullmatch(r"[0-9a-f]{40}", source_revision):
        raise ResourceBundleError("caller must pin package version and source revision")
    try:
        with ZipFile(bundle) as archive:
            infos = archive.infolist()
            names = [info.filename for info in infos]
            if (not names or len(set(names)) != len(names)
                    or "RESOURCE_MANIFEST.json" not in names
                    or "pyproject.toml" not in names):
                raise ResourceBundleError("missing or duplicated bundle member")
            if any(not _safe_path(name) or name.endswith("/") for name in names):
                raise ResourceBundleError("unsafe archive member path")
            portable_names = {_portable_path_key(name) for name in names}
            if len(portable_names) != len(names):
                raise ResourceBundleError("portable archive path collision")
            # Every member is a regular file. A file that is also an
            # ancestor of another member would fail midway through extraction,
            # potentially leaving a partially written resource root. Compare
            # portable keys to catch case-insensitive prefix aliases too.
            for name in portable_names:
                parts = name.split("/")
                if any("/".join(parts[:index]) in portable_names
                       for index in range(1, len(parts))):
                    raise ResourceBundleError("archive file/directory path conflict")
            if any(stat.S_IFMT(info.external_attr >> 16) == stat.S_IFLNK for info in infos):
                raise ResourceBundleError("archive symlinks are forbidden")
            if any(info.file_size > 16 * 1024 * 1024 for info in infos) or sum(
                info.file_size for info in infos
            ) > 128 * 1024 * 1024:
                raise ResourceBundleError("resource archive exceeds bounded extraction size")
            manifest = json.loads(
                archive.read("RESOURCE_MANIFEST.json"), object_pairs_hook=_unique_object,\n                parse_constant=_reject_nonfinite_json, parse_float=_finite_json_float
            )
            if not isinstance(manifest, dict) or set(manifest) != {
                "schema_version", "distribution", "version", "source_revision",
                "resources", "files_sha256",
            }:
                raise ResourceBundleError("invalid resource manifest structure")
            if (type(manifest["schema_version"]) is not int or manifest["schema_version"] != 1
                    or manifest["distribution"] != "codeqa-resource-bundle"
                    or manifest["version"] != version
                    or manifest["source_revision"] != source_revision):
                raise ResourceBundleError("bundle identity/version/source mismatch")
            registry, hashes = manifest["resources"], manifest["files_sha256"]
            if not isinstance(registry, dict) or len(registry) < 2 or not isinstance(hashes, dict):
                raise ResourceBundleError("missing resource registry or digests")
            if set(names) != set(hashes) | {"RESOURCE_MANIFEST.json"}:
                raise ResourceBundleError("bundle members and hashed manifest disagree")
            config = tomllib.loads(archive.read("pyproject.toml").decode("utf-8"))
            if (config.get("project", {}).get("name") != "codeqa"
                    or config.get("project", {}).get("version") != version
                    or config.get("tool", {}).get("codeqa", {}).get("resources") != registry):
                raise ResourceBundleError("bundled registry/package metadata mismatch")
            approved = {"pyproject.toml"}
            for resource_id, path in registry.items():
                if (not isinstance(resource_id, str)
                        or not re.fullmatch(r"[a-z][a-z0-9_]*", resource_id)
                        or not _safe_path(path)
                        or path.split("/")[0] not in {"profiles", "contracts"}):
                    raise ResourceBundleError("unapproved resource ID or path")
                approved.add(path)
            if set(hashes) != approved:
                raise ResourceBundleError("unregistered or missing resource files")
            payloads = {}
            for name in sorted(hashes):
                digest = hashes[name]
                if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
                    raise ResourceBundleError("invalid declared SHA-256")
                data = archive.read(name)
                if sha256(data).hexdigest() != digest:
                    raise ResourceBundleError("resource content SHA-256 mismatch: " + name)
                # A self-consistent manifest can hash invalid JSON bytes.
                # Validate registered JSON resources before extracting any file;
                # the caller still owns schema/policy interpretation.
                if name != "pyproject.toml":
                    try:
                        json.loads(
                            data.decode("utf-8"), object_pairs_hook=_unique_object,
                            parse_constant=_reject_nonfinite_json, parse_float=_finite_json_float,
                        )
                    except (UnicodeError, json.JSONDecodeError) as exc:
                        raise ResourceBundleError(
                            "malformed registered JSON resource: " + name
                        ) from exc
                payloads[name] = data
    except (BadZipFile, OSError, KeyError, UnicodeError, json.JSONDecodeError, tomllib.TOMLDecodeError) as exc:
        raise ResourceBundleError("unreadable or malformed resource archive") from exc
    destination = Path(destination)
    if destination.is_symlink() or any(parent.is_symlink() for parent in destination.parents):
        raise ResourceBundleError("resource extraction destination must not traverse symlinks")
    if destination.exists() and (not destination.is_dir() or any(destination.iterdir())):
        raise ResourceBundleError("destination must be an empty isolated directory")
    destination.mkdir(parents=True, exist_ok=True)
    for name, data in payloads.items():
        target = destination.joinpath(*name.split("/"))
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    return manifest
