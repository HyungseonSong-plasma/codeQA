"""B5: conservative, read-only migration and public-import impact evidence.

The caller supplies bytes from the same immutable Git snapshot as B1--B4.
This is a static impact inventory, not a rewrite plan, ABI proof or permission
to move modules. No package names or desired architecture are hard-coded.
"""
from __future__ import annotations

import ast
from collections.abc import Mapping
from hashlib import sha256
import json
from typing import Any


class ArchitectureMigrationError(ValueError):
    """Invalid, stale, contradictory or untrusted migration input."""


def _digest(value: Any) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _module(path: str) -> str | None:
    if not path.startswith("src/") or not path.endswith(".py"):
        return None
    parts = path[4:-3].split("/")
    if parts[-1] == "__init__":
        parts.pop()
    if not parts or not all(p.isidentifier() for p in parts):
        return None
    return ".".join(parts)


def _matches(name: str, old: str) -> bool:
    return name == old or name.startswith(old + ".")


def _relative(package: str, level: int, module: str | None) -> str | None:
    parts = package.split(".")
    if level > len(parts):
        return None
    prefix = parts[:len(parts) - level + 1]
    return ".".join([*prefix, *module.split(".") if module else []])


def _record(path: str, line: int, kind: str, detail: str, digest: str,
            old: str, new: str, status: str) -> dict[str, Any]:
    return {
        "path": path, "line": line, "kind": kind, "expression": detail,
        "source_sha256": digest, "old_module": old, "proposed_module": new,
        "rewrite_status": status, "evidence_class": "SOURCE_STATIC_WITNESS",
    }


def assess_architecture_migration(
    inventory: Mapping[str, Any],
    scenarios: Mapping[str, Any],
    source_texts: Mapping[str, str | bytes],
) -> dict[str, Any]:
    """Assess B4 candidates against caller-attested B1 source bytes.

    A B4 report's self-digest is checked, but not mistaken for independent
    authentication of the B2/B3 derivation. A trusted caller must supply those
    exact-head reports and independently validate them before invoking B5.
    """
    try:
        if not all(isinstance(x, Mapping) for x in (inventory, scenarios, source_texts)):
            raise ArchitectureMigrationError("mapping inputs required")
        files = inventory["files"]
        by_path = {item["path"]: item for item in files}
        identity = inventory["source_identity"]
        if (len(by_path) != len(files)
                or inventory["inventory_id"] != _digest({
                    k: v for k, v in inventory.items() if k != "inventory_id"
                })
                or scenarios["scenarios_id"] != _digest({
                    k: v for k, v in scenarios.items() if k != "scenarios_id"
                })
                or scenarios["snapshot_sha"] != identity["repository_commit_sha"]
                or scenarios["inventory_id"] != inventory["inventory_id"]
                or scenarios["role_policy_sha256"] != identity["role_policy_sha256"]
                or not isinstance(scenarios["candidates"], list)
                or not isinstance(scenarios["rejected"], list)
                or not set(source_texts) <= set(by_path)):
            raise ArchitectureMigrationError("B1/B4 identity or source scope mismatch")
        decoded: dict[str, str] = {}
        hashes: dict[str, str] = {}
        for path, raw in source_texts.items():
            if by_path[path]["read_state"] != "READ" or not isinstance(raw, (str, bytes)):
                raise ArchitectureMigrationError("unread or non-text source supplied")
            payload = raw.encode("utf-8") if isinstance(raw, str) else raw
            if sha256(payload).hexdigest() != by_path[path]["source_sha256"]:
                raise ArchitectureMigrationError("source hash differs from B1 snapshot")
            hashes[path] = sha256(payload).hexdigest()
            try:
                decoded[path] = payload.decode("utf-8")
            except UnicodeDecodeError:
                # Non-text resources can be present but cannot support text evidence.
                continue
        if any(item["read_state"] == "READ" and item["language"] == "python"
               and item["path"] not in decoded
               for item in files if item["path"] in {
                   move["from"] for candidate in scenarios["candidates"]
                   for move in candidate["path_mapping"]
               }):
            raise ArchitectureMigrationError("moved Python source bytes missing")
    except (KeyError, TypeError, AttributeError, ValueError) as exc:
        raise ArchitectureMigrationError("untrustworthy B1/B4 migration inputs") from exc

    missing = sorted(item["path"] for item in files
                     if item["read_state"] == "READ" and item["path"] not in decoded)
    python_paths = sorted(p for p in decoded if p.endswith(".py"))
    trees: dict[str, ast.AST] = {}
    syntax_errors: list[str] = []
    for path in python_paths:
        try:
            trees[path] = ast.parse(decoded[path], filename=path)
        except SyntaxError:
            syntax_errors.append(path)
    modules = {_module(p): p for p in by_path if _module(p)}
    results: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    for candidate in scenarios["candidates"]:
        try:
            if (candidate["scenario_id"] != _digest({
                    k: v for k, v in candidate.items() if k != "scenario_id"
                }) or candidate["source_identity"]["snapshot_sha"] != scenarios["snapshot_sha"]
                or candidate["source_identity"]["inventory_id"] != inventory["inventory_id"]
                or candidate["source_identity"]["metrics_id"] != scenarios["metrics_id"]
                or candidate["source_identity"]["role_policy_sha256"] != scenarios["role_policy_sha256"]
                or candidate["source_identity"]["dependency_profile_id"] != scenarios["dependency_profile_id"]
                or candidate["scenario_id"] in seen_ids):
                raise ArchitectureMigrationError("invalid candidate identity")
            seen_ids.add(candidate["scenario_id"])
            path_map = {move["from"]: move["to"] for move in candidate["path_mapping"]}
            if len(path_map) != len(candidate["path_mapping"]) or not path_map:
                raise ArchitectureMigrationError("invalid or empty B4 mapping")
            old_to_new: dict[str, str] = {}
            for move in candidate["path_mapping"]:
                old, new = move["from"], move["to"]
                if (old not in by_path or by_path[old]["source_sha256"] != move["source_sha256"]
                        or old not in decoded or _module(old) is None or _module(new) is None):
                    raise ArchitectureMigrationError("unverified moved source/module")
                old_to_new[_module(old)] = _module(new)
            if len(old_to_new) != len(path_map):
                raise ArchitectureMigrationError("duplicate dotted module identity")
        except (KeyError, TypeError, ValueError) as exc:
            raise ArchitectureMigrationError("invalid B4 candidate") from exc

        # A path can be free while its Python module name collides with an
        # existing namespace package or __init__.py; block this independently.
        conflicts = sorted({
            new for old, new in old_to_new.items()
            if new in modules and modules[new] not in path_map
        })
        sites: list[dict[str, Any]] = []
        risk_flags: set[str] = set()
        exported_paths: set[str] = set()
        for path, tree in trees.items():
            source_module = _module(path)
            if source_module is None:
                continue
            package = source_module if path.endswith("/__init__.py") else source_module.rpartition(".")[0]
            moved_source = path in path_map
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        for old, new in old_to_new.items():
                            if _matches(alias.name, old):
                                kind = "ALIASED_IMPORT" if alias.asname else "STATIC_IMPORT"
                                sites.append(_record(path, node.lineno, kind,
                                    alias.name, hashes[path], old, new, "REVIEW_REQUIRED"))
                                if alias.asname:
                                    risk_flags.add("ALIASED_IMPORT_REVIEW")
                elif isinstance(node, ast.ImportFrom):
                    resolved = (_relative(package, node.level, node.module)
                                if node.level else (node.module or ""))
                    if resolved is None:
                        risk_flags.add("UNRESOLVED_RELATIVE_IMPORT")
                        continue
                    for alias in node.names:
                        target = resolved + "." + alias.name if resolved else alias.name
                        for old, new in old_to_new.items():
                            if (_matches(resolved, old) or _matches(target, old)
                                    or (moved_source and node.level > 0)):
                                if alias.name == "*":
                                    kind = "STAR_IMPORT"
                                    risk_flags.add("STAR_IMPORT_REVIEW")
                                elif node.level:
                                    kind = "RELATIVE_IMPORT"
                                    risk_flags.add("RELATIVE_IMPORT_REVIEW")
                                elif alias.asname:
                                    kind = "ALIASED_FROM_IMPORT"
                                    risk_flags.add("ALIASED_IMPORT_REVIEW")
                                else:
                                    kind = "FROM_IMPORT"
                                sites.append(_record(path, node.lineno, kind,
                                    ("." * node.level) + (node.module or "") + ":" + alias.name,
                                    hashes[path], old, new, "REVIEW_REQUIRED"))
                                if path.endswith("/__init__.py"):
                                    exported_paths.add(path)
                                    risk_flags.add("INIT_REEXPORT_REVIEW")
                elif isinstance(node, ast.Call):
                    f = node.func
                    func = f.id if isinstance(f, ast.Name) else (
                        f.value.id + "." + f.attr if isinstance(f, ast.Attribute)
                        and isinstance(f.value, ast.Name) else "")
                    if func not in {"__import__", "importlib.import_module", "pkgutil.resolve_name"}:
                        continue
                    value = (node.args[0].value if node.args and isinstance(
                        node.args[0], ast.Constant) and isinstance(node.args[0].value, str)
                        else None)
                    for old, new in old_to_new.items():
                        if value is None:
                            risk_flags.add("DYNAMIC_IMPORT_TARGET_UNKNOWN")
                        elif _matches(value, old):
                            sites.append(_record(path, node.lineno, "DYNAMIC_IMPORT_LITERAL",
                                value, hashes[path], old, new, "REVIEW_REQUIRED"))
                            risk_flags.add("DYNAMIC_IMPORT_REVIEW")
                elif (path.endswith("/__init__.py") and isinstance(node, ast.Assign)
                      and any(isinstance(t, ast.Name) and t.id == "__all__"
                              for t in node.targets)):
                    if any(source_module == old.rpartition(".")[0]
                           for old in old_to_new):
                        exported_paths.add(path)
                        risk_flags.add("INIT_ALL_EXPORT_REVIEW")

        # Non-Python consumers can contain import references, entrypoints,
        # package metadata, resource mappings or documentation links.
        for path, value in sorted(decoded.items()):
            if path.endswith(".py") and path.startswith("src/"):
                continue
            is_packaging = path.rsplit("/", 1)[-1] in {
                "pyproject.toml", "setup.cfg", "setup.py", "MANIFEST.in"
            }
            for number, line in enumerate(value.splitlines(), 1):
                for old, new in old_to_new.items():
                    if old in line or old.replace(".", "/") in line:
                        kind = ("PACKAGING_REFERENCE" if is_packaging
                                else "TEST_OR_SCRIPT_REFERENCE" if path.endswith(".py")
                                else "CONFIG_OR_DOC_REFERENCE")
                        sites.append(_record(path, number, kind, line.strip()[:240],
                                             hashes[path], old, new, "REVIEW_REQUIRED"))
                        if is_packaging:
                            risk_flags.add("PACKAGE_METADATA_REVIEW")
                        if "script" in line.lower() or "entry" in line.lower():
                            risk_flags.add("CLI_ENTRYPOINT_REVIEW")
        if conflicts:
            risk_flags.add("DOTTED_MODULE_NAMESPACE_COLLISION")
        if any(path not in decoded for path in inventory["package_metadata_paths"]):
            risk_flags.add("PACKAGE_METADATA_NOT_FULLY_OBSERVED")
        if syntax_errors:
            risk_flags.add("PYTHON_PARSE_GAPS")
        if missing:
            risk_flags.add("SOURCE_COVERAGE_GAPS")
        if any(item["read_state"] != "READ" for item in files):
            risk_flags.add("INVENTORY_UNREAD_PATHS")
        risk_flags.add("EXTERNAL_CONSUMERS_UNOBSERVED")
        risk_flags.add("RUNTIME_ABI_SEMANTICS_NOT_EVALUATED")
        risk_flags.add("DISTRIBUTION_AND_RESOURCE_RELOCATION_NOT_EVALUATED")
        if any(old.split(".")[0] != new.split(".")[0]
               for old, new in old_to_new.items()):
            risk_flags.add("CROSS_TOP_LEVEL_PACKAGE_DISTRIBUTION_UNKNOWN")
        sites.sort(key=lambda s: (s["path"], s["line"], s["kind"], s["old_module"]))
        count = len(sites)
        if conflicts:
            cost = "BLOCKED"
        elif count > 10 or any(x in risk_flags for x in (
                "STAR_IMPORT_REVIEW", "CLI_ENTRYPOINT_REVIEW",
                "DOTTED_MODULE_NAMESPACE_COLLISION",
                "CROSS_TOP_LEVEL_PACKAGE_DISTRIBUTION_UNKNOWN")):
            cost = "HIGH"
        elif count > 2 or len(path_map) > 1 or any(x in risk_flags for x in (
                "DYNAMIC_IMPORT_TARGET_UNKNOWN", "PACKAGE_METADATA_REVIEW",
                "INIT_REEXPORT_REVIEW", "RELATIVE_IMPORT_REVIEW")):
            cost = "MEDIUM"
        else:
            cost = "LOW"
        result = {
            "scenario_id": candidate["scenario_id"],
            "path_mapping": candidate["path_mapping"],
            "observed_sites": sites,
            "observed_site_count": count,
            "affected_file_count": len({s["path"] for s in sites}),
            "moved_file_count": len(path_map),
            "initializer_export_paths": sorted(exported_paths),
            "namespace_collisions": conflicts,
            "cost_band": cost,
            "cost_basis": {
                "static_and_text_reference_sites": count,
                "moved_files": len(path_map),
                "unresolved_risk_flag_count": len(risk_flags),
                "band_rules": "BLOCKED if namespace collision; HIGH if >10 sites or star/CLI/distribution risk; MEDIUM if >2 sites/multi-file or unresolved dynamic/metadata/export/relative; otherwise LOW",
            },
            "compatibility_status": "BLOCKED" if conflicts else "NOT_EVALUATED",
            "confidence": "INSUFFICIENT_EVIDENCE" if missing or syntax_errors else "STATIC_PARTIAL",
            "unknowns": sorted(risk_flags),
            "compatibility_options": [
                "forwarding module or facade subject to independent import tests",
                "versioned deprecation window subject to consumer contract",
                "separate distribution only after packaging and external-caller evidence",
            ],
        }
        results.append(result)

    report = {
        "schema_version": "0.1",
        "snapshot_sha": scenarios["snapshot_sha"],
        "inventory_id": inventory["inventory_id"],
        "scenarios_id": scenarios["scenarios_id"],
        "candidates": sorted(results, key=lambda c: c["scenario_id"]),
        "rejected_scenarios": scenarios["rejected"],
        "source_coverage": {
            "read_source_texts": len(decoded),
            "missing_read_source_texts": missing,
            "python_parse_failures": sorted(syntax_errors),
        },
        "decision": "NOT_EVALUATED",
        "evidence_status": "INCOMPLETE",
        "limitations": [
            "B4 digest is checked, but trusted caller must authenticate upstream B2/B3 provenance",
            "external consumers, runtime ABI and semantic parity are not proven",
            "source scanning is static and cannot guarantee absence of dynamic or downstream imports",
            "cost bands count observable sites and risk flags, not predicted engineering time",
            "no source, import, public API, package or distribution is modified",
        ],
    }
    report["migration_id"] = _digest(report)
    return report
