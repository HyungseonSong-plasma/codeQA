"""Source-only lexical import candidates for B8 architecture review.

A Name(Load) can refer to a shadowed or rebound name. Co-located import
bindings are not target-resolution, runtime-execution or ownership evidence.
"""
from __future__ import annotations

import ast
from collections.abc import Mapping
from hashlib import sha256
import json
import re
from typing import Any


class ImportBindingUsageError(ValueError):
    """Untrusted source identity or import-witness denominator."""


def _digest(value: Any) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _sealed(value: Mapping[str, Any], key: str) -> bool:
    return value[key] == _digest({k: v for k, v in value.items() if k != key})


def census_b8_import_binding_uses(
    selection: Mapping[str, Any],
    responsibility: Mapping[str, Any],
    source_bytes: Mapping[str, bytes],
) -> dict[str, Any]:
    """Enumerate lexical loads on each measured import line, without name resolution."""
    try:
        identity = selection["source_identity"]
        pairs = [tuple(pair) for pair in selection["pairs"]]
        edges = {(e["source_path"], e["target_path"]): e
                 for e in responsibility["edges"]}
        sources = {src for src, _ in pairs}
        hashes = selection["source_sha256"]
        if (selection["schema_version"] != "0.1"
                or responsibility["schema_version"] != "0.1"
                or not _sealed(selection, "selection_id")
                or not _sealed(responsibility, "responsibility_id")
                or identity["snapshot_sha"] != responsibility["source_identity"]["snapshot_sha"]
                or identity["responsibility_id"] != responsibility["responsibility_id"]
                or selection["decision"] != "NOT_EVALUATED"
                or responsibility["decision"] != "NOT_EVALUATED"
                or selection["observed_cross_role_pairs"] != len(pairs)
                or responsibility["observed_cross_role_pairs"] != len(edges)
                or len(pairs) != len(set(pairs))
                or len(edges) != len(responsibility["edges"])
                or set(pairs) != set(edges)
                or set(source_bytes) != sources
                or set(hashes) != {path for pair in pairs for path in pair}
                or not re.fullmatch(r"[0-9a-f]{40}", identity["snapshot_sha"])):
            raise ImportBindingUsageError("unbound source or pair denominator")

        import_nodes: dict[str, dict[int, list[ast.Import | ast.ImportFrom]]] = {}
        loads: dict[str, dict[str, list[dict[str, int]]]] = {}
        for path in sorted(sources):
            raw = source_bytes[path]
            if not isinstance(raw, bytes) or sha256(raw).hexdigest() != hashes[path]:
                raise ImportBindingUsageError("source bytes do not match pinned hash")
            tree = ast.parse(raw, filename=path)
            by_line: dict[int, list[ast.Import | ast.ImportFrom]] = {}
            by_name: dict[str, list[dict[str, int]]] = {}
            for node in ast.walk(tree):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    by_line.setdefault(node.lineno, []).append(node)
                elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                    by_name.setdefault(node.id, []).append({
                        "line": node.lineno, "column": node.col_offset,
                    })
            import_nodes[path] = by_line
            loads[path] = by_name

        records = []
        for src, dst in sorted(pairs):
            witnesses = edges[(src, dst)]["import_witnesses"]
            if (not isinstance(witnesses, list) or not witnesses
                    or any(w["source_path"] != src
                           or w["target_path"] != dst
                           or w["source_sha256"] != hashes[src]
                           or type(w["line"]) is not int or w["line"] < 1
                           for w in witnesses)):
                raise ImportBindingUsageError("unbound static import witnesses")
            lines = sorted({w["line"] for w in witnesses})
            candidates = []
            for line in lines:
                nodes = import_nodes[src].get(line, [])
                if not nodes:
                    raise ImportBindingUsageError("witness line is not an AST import")
                for node in nodes:
                    for alias in node.names:
                        if isinstance(node, ast.ImportFrom):
                            name = alias.asname or alias.name
                        else:
                            name = alias.asname or alias.name.split(".")[0]
                        if name == "*":
                            candidates.append({
                                "line": line, "name": None, "lexical_load_count": 0,
                                "load_witnesses": [], "status": "STAR_IMPORT_UNRESOLVED",
                            })
                            continue
                        positions = sorted(loads[src].get(name, []),
                                           key=lambda x: (x["line"], x["column"]))
                        candidates.append({
                            "line": line, "name": name,
                            "lexical_load_count": len(positions),
                            "load_witnesses": positions[:8],
                            "status": ("NAME_LOAD_CANDIDATE" if positions
                                       else "NO_NAME_LOAD_IN_SOURCE"),
                        })
            records.append({
                "source_path": src,
                "target_path": dst,
                "source_sha256": hashes[src],
                "import_lines": lines,
                "candidate_bindings": candidates,
                "has_name_load_candidate": any(c["lexical_load_count"] for c in candidates),
                "binding_target_attribution": "LINE_COLOCATED_UNVERIFIED",
                "import_execution": "NOT_EVALUATED",
                "semantic_ownership": "NOT_EVALUATED",
            })
        result = {
            "schema_version": "0.1",
            "source_identity": identity,
            "selection_id": selection["selection_id"],
            "responsibility_id": responsibility["responsibility_id"],
            "static_pairs": len(records),
            "pairs_with_name_load_candidates": sum(x["has_name_load_candidate"] for x in records),
            "pairs_without_name_load_candidates": sum(not x["has_name_load_candidate"] for x in records),
            "records": records,
            "evidence_class": "SOURCE_ONLY_LEXICAL_CANDIDATE_UNATTESTED",
            "import_execution": "NOT_EVALUATED",
            "semantic_ownership": "NOT_EVALUATED",
            "external_consumers": "NOT_EVALUATED",
            "public_api_compatibility": "NOT_EVALUATED",
            "decision": "NOT_EVALUATED",
            "limitations": [
                "import-line co-location does not attribute an alias to the target module",
                "lexical Name(Load) may be shadowed or rebound and is not runtime use proof",
                "no Name(Load) does not prove an import is unused or safe to remove",
                "annotations, reflection, wildcard and dynamic imports are not resolved",
                "external callers and package/public API compatibility remain unknown",
            ],
        }
        result["usage_id"] = _digest(result)
        return result
    except (KeyError, TypeError, AttributeError, ValueError, SyntaxError) as exc:
        raise ImportBindingUsageError("invalid import binding usage evidence") from exc
