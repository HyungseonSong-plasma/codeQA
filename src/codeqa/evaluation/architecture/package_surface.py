"""Bounded distribution/package exposure for B3-derived architecture modules.

This is a declaration-and-static-consumer census, not a public API promise,
installed-wheel proof, external-caller scan, or authorization to relocate code.
"""
from __future__ import annotations

from collections.abc import Mapping
from fnmatch import fnmatchcase
from hashlib import sha256
import json
import tomllib
from typing import Any


class PackageSurfaceEvidenceError(ValueError):
    """Untrusted snapshot, package declaration, or consumer evidence."""


def _digest(value: Any) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def census_package_surface(
    inventory: Mapping[str, Any],
    consumers: Mapping[str, Any],
    pyproject: bytes | str,
) -> dict[str, Any]:
    """Bind a tracked pyproject to B1/B2/B3 consumer evidence at one HEAD.

    Setuptools package discovery is a *declared* distribution configuration.
    Import names are potential import paths, not supported external APIs.
    """
    try:
        if not isinstance(pyproject, (bytes, str)):
            raise PackageSurfaceEvidenceError("pyproject source bytes required")
        raw = pyproject.encode("utf-8") if isinstance(pyproject, str) else pyproject
        config = tomllib.loads(raw.decode("utf-8"))
        tracked = {item["path"]: item for item in inventory["files"]}
        source = inventory["source_identity"]["repository_commit_sha"]
        identity = consumers["source_identity"]
        if (
            inventory["schema_version"] != "0.1"
            or consumers["schema_version"] != "0.1"
            or inventory["inventory_id"] != _digest({
                k: v for k, v in inventory.items() if k != "inventory_id"
            })
            or consumers["census_id"] != _digest({
                k: v for k, v in consumers.items() if k != "census_id"
            })
            or identity["snapshot_sha"] != source
            or identity["inventory_id"] != inventory["inventory_id"]
            or consumers["decision"] != "NOT_EVALUATED"
            or len(tracked) != len(inventory["files"])
            or tracked["pyproject.toml"]["read_state"] != "READ"
            or tracked["pyproject.toml"]["source_sha256"] != sha256(raw).hexdigest()
            or len({m["module_path"] for m in consumers["modules"]})
               != len(consumers["modules"])
            or consumers["concentration_source_modules"] != len(consumers["modules"])
            or consumers["known_static_importer_pairs"] != sum(
                m["known_static_importer_pairs"] for m in consumers["modules"]
            )
            or consumers["known_test_path_importer_pairs"] != sum(
                m["known_test_path_importer_pairs"] for m in consumers["modules"]
            )
        ):
            raise PackageSurfaceEvidenceError("snapshot/consumer/pyproject mismatch")
        scope = inventory["source_scope"]
        parts = scope.split("/")
        if len(parts) < 2 or not all(parts):
            raise PackageSurfaceEvidenceError("invalid source scope")
        where = parts[0]
        root_name = ".".join(parts[1:])
        find = config.get("tool", {}).get("setuptools", {}).get("packages", {}).get("find", {})
        if not isinstance(find, dict):
            raise PackageSurfaceEvidenceError("invalid package discovery declaration")
        search_roots = find.get("where", [])
        includes = find.get("include", ["*"])
        excludes = find.get("exclude", [])
        if not all(isinstance(v, list) and all(isinstance(x, str) for x in v)
                   for v in (search_roots, includes, excludes)):
            raise PackageSurfaceEvidenceError("invalid package discovery patterns")
        # setuptools applies include/exclude to each discovered package name,
        # not just the top-level root. Parent packages may be excluded while
        # a child package is still selected; do not infer wheel importability.
        modules = []
        for module in sorted(consumers["modules"], key=lambda item: item["module_path"]):
            path = module["module_path"]
            if path not in tracked or not path.startswith(scope + "/") or not path.endswith(".py"):
                raise PackageSurfaceEvidenceError("consumer module outside source scope")
            if module["known_static_importer_pairs"] != len(module["importers"]):
                raise PackageSurfaceEvidenceError("inconsistent importer count")
            if module["known_test_path_importer_pairs"] != sum(
                i["importer_category"] == "TEST_PATH_HEURISTIC"
                for i in module["importers"]
            ):
                raise PackageSurfaceEvidenceError("inconsistent test-path importer count")
            relative = path[len(where) + 1:]
            if path.endswith("/__init__.py"):
                import_name = relative[:-len("/__init__.py")].replace("/", ".")
                package_path = path[:-len("/__init__.py")]
            else:
                import_name = relative[:-3].replace("/", ".")
                package_path = path.rsplit("/", 1)[0]
            parent_parts = package_path.split("/")
            init_paths = [
                "/".join(parent_parts[:i]) + "/__init__.py"
                for i in range(2, len(parent_parts) + 1)
            ]
            init_coverage = all(
                p in tracked and tracked[p]["read_state"] == "READ"
                for p in init_paths
            )
            # Match the containing package, not the .py module or root only.
            # An excluded parent can coexist with an included child in the
            # declared find_packages selection; runtime imports stay unknown.
            package_name = ".".join(parent_parts[1:])
            declared_package = (
                where in search_roots
                and any(fnmatchcase(package_name, pattern) for pattern in includes)
                and not any(fnmatchcase(package_name, pattern) for pattern in excludes)
            )
            status = (
                "DECLARED_DISCOVERY_CANDIDATE"
                if declared_package and init_coverage
                and tracked[path]["read_state"] == "READ"
                else "NOT_EVALUATED"
            )
            modules.append({
                "module_path": path,
                "potential_import_name": import_name,
                "source_sha256": tracked[path]["source_sha256"],
                "package_initializer_paths": init_paths,
                "declared_discovery_status": status,
                "known_static_importer_pairs": module["known_static_importer_pairs"],
                "known_test_path_importer_pairs": module["known_test_path_importer_pairs"],
                "external_import_compatibility": "NOT_EVALUATED",
                "supported_public_api": "NOT_EVALUATED",
            })
        project = config.get("project", {})
        if not isinstance(project, dict) or not isinstance(project.get("name"), str):
            raise PackageSurfaceEvidenceError("missing project distribution name")
        result = {
            "schema_version": "0.1",
            "source_identity": {
                "snapshot_sha": source,
                "inventory_id": inventory["inventory_id"],
                "consumer_census_id": consumers["census_id"],
                "pyproject_sha256": sha256(raw).hexdigest(),
            },
            "distribution_name": project["name"],
            "declaration_path": "pyproject.toml",
            "declaration_kind": "SETUPTOOLS_FIND",
            "declared_find": {
                "where": search_roots, "include": includes, "exclude": excludes,
            },
            "source_scope": scope,
            "modules": modules,
            "declared_discovery_candidates": sum(
                m["declared_discovery_status"] == "DECLARED_DISCOVERY_CANDIDATE"
                for m in modules
            ),
            "external_consumers": "NOT_EVALUATED",
            "installed_distribution": "NOT_EVALUATED",
            "runtime_imports": "NOT_EVALUATED",
            "public_api_compatibility": "NOT_EVALUATED",
            "decision": "NOT_EVALUATED",
            "limitations": [
                "setuptools include/exclude patterns are checked per containing package",
                "setuptools find configuration is declared intent, not a built-wheel file inventory",
                "potential import names are not a supported public API contract",
                "known B2 static importers are not exhaustive consumers or behavioral tests",
                "external callers, dynamic imports, re-exports and runtime compatibility remain unverified",
                "no package move or quality PASS is authorized by this census",
            ],
        }
        result["surface_id"] = _digest(result)
        return result
    except (KeyError, TypeError, AttributeError, UnicodeError, ValueError, tomllib.TOMLDecodeError) as exc:
        raise PackageSurfaceEvidenceError("untrustworthy package surface evidence") from exc


def render_package_surface_markdown(surface: Mapping[str, Any]) -> str:
    """Render bounded packaging evidence without claiming public compatibility."""
    try:
        if surface["surface_id"] != _digest({
            k: v for k, v in surface.items() if k != "surface_id"
        }):
            raise PackageSurfaceEvidenceError("modified package surface report")
        lines = [
            "## Declared package discovery and potential import surfaces",
            "",
            "Exact source HEAD: " + surface["source_identity"]["snapshot_sha"],
            "Distribution declaration: " + surface["declaration_path"]
            + " (sha256=" + surface["source_identity"]["pyproject_sha256"] + ")",
            "Distribution: " + surface["distribution_name"],
            "Declared discovery candidates: "
            + str(surface["declared_discovery_candidates"])
            + "/" + str(len(surface["modules"])),
            "Potential import paths are NOT supported public API or installed-wheel proof.",
        ]
        for module in surface["modules"]:
            lines.append(
                "- `" + module["potential_import_name"] + "` from `"
                + module["module_path"] + "` ("
                + module["declared_discovery_status"] + "; static importers="
                + str(module["known_static_importer_pairs"]) + ")"
            )
        lines.extend([
            "",
            "External callers, dynamic imports, installed distribution and runtime "
            "compatibility: NOT_EVALUATED.",
            "",
        ])
        return "\n".join(lines)
    except (KeyError, TypeError, AttributeError, ValueError) as exc:
        raise PackageSurfaceEvidenceError("untrustworthy package surface report") from exc
