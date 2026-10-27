"""Read-only, question-agnostic architecture tree and source coverage evidence."""
from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping
from hashlib import sha256
import json
import re
from typing import Any

from codeqa.evaluation.semantic_layout import evaluate_semantic_layout


class ArchitectureInventoryError(ValueError):
    """Untrustworthy snapshot, path, ownership policy or hint."""


def _digest(value: Any) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _valid_path(path: Any) -> bool:
    return (
        isinstance(path, str) and bool(path) and not path.startswith("/")
        and "\\" not in path and ":" not in path
        and not any(ord(ch) < 32 or ord(ch) == 127 for ch in path)
        and all(part not in ("", ".", "..") and not part.endswith((".", " "))
                for part in path.split("/"))
    )


def _language(path: str) -> str:
    suffix = path.rsplit(".", 1)[-1] if "." in path else ""
    if suffix == "py":
        return "python"
    if suffix == "rs":
        return "rust"
    if suffix in {"c", "h", "cc", "cpp", "cxx", "hpp", "hxx"}:
        return "cpp_family"
    return "other"


def _hints(rules: Iterable[Mapping[str, str]]) -> tuple[tuple[str, re.Pattern[str]], ...]:
    parsed: list[tuple[str, re.Pattern[str]]] = []
    names: set[str] = set()
    for item in rules:
        if not isinstance(item, Mapping) or set(item) != {"domain", "pattern"}:
            raise ArchitectureInventoryError("invalid name-hint rule")
        name, pattern = item["domain"], item["pattern"]
        if (not isinstance(name, str) or not name or name in names
                or not isinstance(pattern, str) or not pattern or len(pattern) > 200):
            raise ArchitectureInventoryError("invalid or duplicate hint domain")
        try:
            regex = re.compile(pattern)
        except re.error as exc:
            raise ArchitectureInventoryError("invalid hint regex") from exc
        names.add(name)
        parsed.append((name, regex))
    return tuple(sorted(parsed, key=lambda item: item[0]))


def analyze_architecture_inventory(
    snapshot_sha: str,
    tracked_paths: Iterable[str],
    sources: Mapping[str, bytes | str],
    role_policy: Mapping[str, Any],
    *,
    excluded_paths: Iterable[str] = (),
    failed_paths: Iterable[str] = (),
    symlink_paths: Iterable[str] = (),
    generated_paths: Iterable[str] = (),
    name_hint_rules: Iterable[Mapping[str, str]] = (),
) -> dict[str, Any]:
    """Inventory a caller-attested exact Git snapshot without reading files.

    The tracked path set is the coverage denominator. A path without bytes is
    MISSING, not omitted. Callers must classify Git mode 120000 as a symlink;
    this evaluator never follows a symlink. Source content is never parsed.
    """
    if not isinstance(snapshot_sha, str) or not re.fullmatch(r"[0-9a-f]{40}", snapshot_sha):
        raise ArchitectureInventoryError("exact lowercase 40-character Git SHA required")
    if not isinstance(sources, Mapping) or not isinstance(role_policy, Mapping):
        raise ArchitectureInventoryError("source and policy mappings required")
    paths = tuple(tracked_paths)
    if not paths or len(set(paths)) != len(paths) or not all(_valid_path(p) for p in paths):
        raise ArchitectureInventoryError("invalid, duplicate or empty tracked paths")
    expected = set(paths)
    flags = {
        "EXCLUDED": set(excluded_paths),
        "READ_FAILED": set(failed_paths),
        "SYMLINK_NOT_FOLLOWED": set(symlink_paths),
    }
    generated = set(generated_paths)
    if any(not isinstance(p, str) for p in generated):
        raise ArchitectureInventoryError("invalid generated path")
    if any(not selected <= expected for selected in (*flags.values(), generated, set(sources))):
        raise ArchitectureInventoryError("untracked source or classification path")
    if any(flags[a] & flags[b] for a in flags for b in flags if a < b):
        raise ArchitectureInventoryError("overlapping source exclusion states")
    if set(sources) & set().union(*flags.values()):
        raise ArchitectureInventoryError("excluded/failed/symlink sources must not be read")
    if any(not isinstance(content, (str, bytes)) for content in sources.values()):
        raise ArchitectureInventoryError("source bytes or text required")

    # Reuse the existing role-policy validator. Import edges are not assessed.
    try:
        evaluate_semantic_layout(paths, (), role_policy)
    except (ValueError, TypeError, KeyError) as exc:
        raise ArchitectureInventoryError("incompatible role policy") from exc
    root = role_policy["scope"]
    roles = role_policy["roles"]
    hints = _hints(name_hint_rules)

    files: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()
    unknown: Counter[str] = Counter()
    languages: dict[str, Counter[str]] = {}
    directory_stats: dict[str, dict[str, int]] = {}
    for path in sorted(paths):
        state = next((name for name, selected in flags.items() if path in selected), None)
        if state is None:
            state = "READ" if path in sources else "MISSING"
        counts[state] += 1
        if path in generated:
            counts["GENERATED"] += 1
        if state != "READ":
            unknown[state] += 1

        if path.startswith(root + "/"):
            relative = path[len(root) + 1:]
            role = relative.split("/")[0]
            declared = role in roles and "/" in relative
        else:
            role, declared = None, False
        matched = [name for name, regex in hints if regex.search(path)]
        ownership = (
            "POLICY_DECLARED" if declared else
            "AMBIGUOUS" if len(matched) > 1 else
            "NAME_HINT" if len(matched) == 1 else
            "UNCLASSIFIED"
        )
        if path.startswith(root + "/") and ownership in {"AMBIGUOUS", "UNCLASSIFIED"}:
            unknown["UNKNOWN_SCOPED_OWNERSHIP"] += 1
        raw = sources[path] if state == "READ" else None
        if isinstance(raw, str):
            raw = raw.encode("utf-8")
        file_hash = sha256(raw).hexdigest() if raw is not None else None
        lang = _language(path)
        bucket = languages.setdefault(lang, Counter())
        bucket["tracked"] += 1
        bucket["read" if state == "READ" else "not_read"] += 1
        files.append({
            "path": path, "source_sha256": file_hash, "read_state": state,
            "language": lang, "parser_status": "NOT_EVALUATED",
            "ownership_class": ownership, "declared_role": role if declared else None,
            "name_hints": matched, "generated": path in generated,
            "evidence_class": "DECLARED_POLICY" if declared else
                              "PROXY_INFERENCE" if matched else "OBSERVED",
        })
        parts = path.split("/")
        for depth in range(len(parts)):
            parent = "." if depth == 0 else "/".join(parts[:depth])
            stats = directory_stats.setdefault(parent, {"descendant_files": 0, "direct_files": 0})
            stats["descendant_files"] += 1
            if depth == len(parts) - 1:
                stats["direct_files"] += 1

    directories = [{
        "path": p,
        "parent": None if p == "." else (p.rsplit("/", 1)[0] if "/" in p else "."),
        "direct_files": stats["direct_files"],
        "descendant_files": stats["descendant_files"],
        "children": sorted(
            child for child in directory_stats
            if child != p and (
                (p == "." and "/" not in child) or
                (p != "." and child.startswith(p + "/")
                 and "/" not in child[len(p) + 1:])
            )
        ),
    } for p, stats in sorted(directory_stats.items())]
    packages = []
    for item in files:
        if not item["path"].endswith("/__init__.py"):
            continue
        parent = item["path"].rsplit("/", 1)[0]
        module_paths = [
            other["path"] for other in files
            if other["path"].startswith(parent + "/")
            and other["path"].endswith(".py")
            and other["path"] != item["path"]
        ]
        packages.append({
            "path": parent, "init_path": item["path"],
            "init_read_state": item["read_state"],
            "module_files": len(module_paths),
            "no_other_python_modules": not module_paths,
            "evidence_class": "OBSERVED",
        })
    hint_manifest = [{"domain": name, "pattern": regex.pattern} for name, regex in hints]
    result = {
        "schema_version": "0.1",
        "source_identity": {
            "repository_commit_sha": snapshot_sha,
            "role_policy_sha256": _digest(role_policy),
            "name_hint_rules_sha256": _digest(hint_manifest),
        },
        "status": "INCOMPLETE" if any(counts[s] for s in flags) or counts["MISSING"]
                  else "EVIDENCE_ONLY",
        "source_scope": root,
        "coverage": {
            "tracked_total": len(paths), "read": counts["READ"],
            "missing": counts["MISSING"], "excluded": counts["EXCLUDED"],
            "failed": counts["READ_FAILED"],
            "symlink_not_followed": counts["SYMLINK_NOT_FOLLOWED"],
            "generated": counts["GENERATED"], "parsed": 0,
        },
        "unknown_reasons": dict(sorted(unknown.items())),
        "files": files, "directories": directories,
        "packages": sorted(packages, key=lambda x: x["path"]),
        "language_coverage": {
            lang: {**dict(sorted(values.items())), "parser_status": "NOT_EVALUATED"}
            for lang, values in sorted(languages.items())
        },
        "package_metadata_paths": [
            path for path in sorted(paths)
            if path in {"pyproject.toml", "setup.py", "setup.cfg", "MANIFEST.in"}
        ],
        "top_level_groups": dict(sorted(Counter(path.split("/")[0] for path in paths).items())),
        "limitations": [
            "tracked-path enumeration and commit SHA are caller-attested, not independently fetched",
            "directory names and filename hints cannot prove semantic responsibility or cohesion",
            "readable source is not parsed, executed or semantically verified by this inventory",
            "external consumers, generated semantics and untracked/empty directories are unknown",
            "symlink targets are not followed and do not count as read source",
        ],
    }
    result["inventory_id"] = _digest(result)
    return result
