#!/usr/bin/env python3
"""Generate a deterministic *separate* registered-resource bundle.

No repo layout contract is changed; no resources are silently embedded in the
codeqa wheel. Only files referenced in pyproject.toml are shipped.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import re
import tomllib
import unicodedata
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED


_WINDOWS_DEVICE_NAMES = {"CON", "PRN", "AUX", "NUL"} | {
    f"{prefix}{n}" for prefix in ("COM", "LPT") for n in range(1, 10)
}


def _safe_path(value: str) -> bool:
    if (not value or value.startswith("/")
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

def generate(root: Path, destination: Path, git_sha: str) -> dict:
    root = root.resolve()
    if not re.fullmatch(r"[0-9a-f]{40}", git_sha):
        raise ValueError("an exact commit SHA is required")
    config_bytes = (root / "pyproject.toml").read_bytes()
    config = tomllib.loads(config_bytes.decode("utf-8"))
    registry = config["tool"]["codeqa"]["resources"]
    if not isinstance(registry, dict) or not registry:
        raise ValueError("missing resource registry")
    paths: set[str] = {"pyproject.toml"}
    for resource_id, relative in registry.items():
        if not re.fullmatch(r"[a-z][a-z0-9_]*", resource_id):
            raise ValueError("invalid resource identifier")
        if not isinstance(relative, str):
            raise ValueError("invalid resource path")
        parts = relative.split("/")
        if (not _safe_path(relative)
                or parts[0] not in {"profiles", "contracts"}):
            raise ValueError("unsafe or unapproved resource path")
        paths.add(relative)
    if len({_portable_path_key(name) for name in paths}) != len(paths):
        raise ValueError("portable resource path collision")
    by_path: dict[str, bytes] = {}
    for name in sorted(paths):
        candidate = root.joinpath(*name.split("/"))
        if candidate.is_symlink() or not candidate.is_file():
            raise ValueError("resource missing or symbolic link")
        if not candidate.resolve().is_relative_to(root):
            raise ValueError("resource escapes checkout")
        by_path[name] = candidate.read_bytes()

    manifest = {
        "schema_version": 1,
        "distribution": "codeqa-resource-bundle",
        "version": config["project"]["version"],
        "source_revision": git_sha,
        "resources": {key: registry[key] for key in sorted(registry)},
        "files_sha256": {
            name: sha256(by_path[name]).hexdigest() for name in sorted(by_path)
        },
    }
    by_path["RESOURCE_MANIFEST.json"] = (
        json.dumps(manifest, sort_keys=True, indent=2) + "\n"
    ).encode("utf-8")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(destination, "w", compression=ZIP_DEFLATED, compresslevel=9) as bundle:
        for name in sorted(by_path):
            info = ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            bundle.writestr(info, by_path[name], compress_type=ZIP_DEFLATED,
                            compresslevel=9)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-revision", required=True)
    args = parser.parse_args()
    manifest = generate(args.root, args.output, args.source_revision)
    print(f"RESOURCE_BUNDLE=PASS files={len(manifest['files_sha256'])} "
          f"version={manifest['version']}")


if __name__ == "__main__":
    main()
