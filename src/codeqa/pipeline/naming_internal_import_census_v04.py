"""Read-only complete pinned codeQA Python source census for #144.

No network, runtime imports of subject code, external-client assertions,
or semantic Naming approval. Selects 100 exact tracked Python source paths
from Git itself, tied to an immutable root tree and SHA1 blob identities.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from hashlib import sha1, sha256
from pathlib import Path
from typing import Any

from codeqa.core.naming_internal_import_graph_v04 import (
    InternalImportGraphError, ORIGIN_MODULE, TARGET,
    classify_static_import_chains, module_for_path, scan_module_imports,
)
from codeqa.core.naming_field_classification_v03 import (
    classify_pinned_class_annotation,
)
from codeqa.infrastructure.git import GitReader
from codeqa.pipeline.naming_scope_discovery_v04 import _tree_manifest


class InternalImportCensusError(ValueError):
    """Wrong tracked source denominator, pinned tree or invented authority."""


def audit_pinned_internal_imports(
    root: Path, charter: Mapping[str, Any],
) -> dict[str, Any]:
    """Re-derive a tracked-file denominator from exact pinned Git tree."""
    keys = {
        "schema_version", "source_commit", "source_tree_sha",
        "source_path_selection", "selected_python_file_count",
        "root_symbol", "root_module", "root_field_owner", "root_field_line",
        "known_direct_clients", "external_callers", "external_deferred_issue",
        "glossary_adoption", "rename_authorized",
    }
    if (not isinstance(charter, Mapping) or set(charter) != keys
            or charter["schema_version"] != "0.4-internal-graph-source-census"
            or charter["source_commit"] != "1b6dd3329a3c6e4fc70602cdaaea9e2fd0698f76"
            or charter["source_tree_sha"] != "c8a8dd5906d33bf49f46c8a2355f2512c225048b"
            or charter["source_path_selection"] != "src/codeqa/**/*.py"
            or type(charter["selected_python_file_count"]) is not int
            or charter["selected_python_file_count"] != 100
            or charter["root_symbol"] != TARGET or charter["root_module"] != ORIGIN_MODULE
            or charter["root_field_owner"] != "ControlFlowObservation"
            or charter["root_field_line"] != 10
            or charter["external_callers"] != "DEFERRED_NO_EVIDENCE"
            or charter["external_deferred_issue"] != 147
            or charter["glossary_adoption"] != "NOT_ADOPTED"
            or charter["rename_authorized"] is not False):
        raise InternalImportCensusError("unapproved or unpinned source charter")
    clients = charter["known_direct_clients"]
    known = (
        {"path": "src/codeqa/adapters/python_complexity.py", "line": 12},
        {"path": "src/codeqa/evaluation/complexity.py", "line": 8},
    )
    if not isinstance(clients, list) or clients != list(known):
        raise InternalImportCensusError("known source controls changed")

    root = Path(root).resolve()
    try:
        tree, git_files = _tree_manifest(root, charter["source_commit"])
    except Exception as exc:
        raise InternalImportCensusError("cannot enumerate historical Git tree") from exc
    if tree != charter["source_tree_sha"] or len(git_files) != 100:
        raise InternalImportCensusError("historical Git selection denominator drift")
    reader = GitReader(root)
    scans: dict[str, dict[str, Any]] = {}
    file_evidence = []
    for path in sorted(git_files):
        raw = reader.read_file(charter["source_commit"], path)
        blob = sha1(b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw).hexdigest()
        if blob != git_files[path]:
            raise InternalImportCensusError("Git blob identity mismatch")
        try:
            scan = scan_module_imports(raw, path=path)
        except InternalImportGraphError as exc:
            raise InternalImportCensusError("cannot parse/identify pinned " + path) from exc
        mod = module_for_path(path)
        if mod in scans:
            raise InternalImportCensusError("duplicate Python module namespace")
        scans[mod] = scan
        file_evidence.append({
            "path": path, "module": mod, "git_blob_sha": blob,
            "source_sha256": sha256(raw).hexdigest(),
            "ast_parse": "PASS",
        })

    owner = "src/codeqa/core/complexity.py"
    if owner not in git_files:
        raise InternalImportCensusError("source owner absent")
    root_bytes = reader.read_file(charter["source_commit"], owner)
    field = classify_pinned_class_annotation(
        root_bytes, expected_sha256=sha256(root_bytes).hexdigest(),
        owner="ControlFlowObservation", name="node_id", line=10,
    )
    if field.classification != "FIELD_CANDIDATE":
        raise InternalImportCensusError("root field evidence not established")
    graph = classify_static_import_chains(scans)
    for example in clients:
        client = module_for_path(example["path"])
        edges = [e for e in graph["target_from_import_edges"]
                 if e["importer"] == client
                 and e["source_module"] == ORIGIN_MODULE
                 and e["imported_name"] == TARGET
                 and e["bound_name"] == TARGET
                 and e["line"] == example["line"]
                 and e["syntax"] == "TOP_LEVEL_FROM"
                 and e["provenance"] == "DIRECT_OR_CHAINED_IMPORT_SYNTAX_CANDIDATE"]
        if len(edges) != 1:
            raise InternalImportCensusError("known source-only client regression")
    count_uncertainties = Counter()
    for item in scans.values():
        count_uncertainties.update(x["reason"] for x in item["unresolved"])
    return {
        "schema_version": "0.4-complete-pinned-internal-target-census",
        "source_commit": charter["source_commit"],
        "source_tree_sha": tree,
        "root_symbol": TARGET, "root_module": ORIGIN_MODULE,
        "root_field_role": "STDLIB_DATACLASS_FIELD_CANDIDATE",
        "selected_source_files": len(git_files),
        "ast_parsed_files": len(scans),
        "total_import_statements": sum(s["import_statement_count"]
                                       for s in scans.values()),
        "source_file_evidence": file_evidence,
        "target_graph": graph,
        "unresolved_syntax_reason_counts": dict(sorted(count_uncertainties.items())),
        "internal_import_scope": "SELECTED_ROOT_SYMBOL_SOURCE_SYNTAX_ONLY",
        "whole_repository_binding_graph": "NOT_EVALUATED",
        "dynamic_import_resolution": "NOT_EVALUATED",
        "external_caller_evidence": "DEFERRED_NO_EVIDENCE",
        "external_deferred_issue": 147,
        "external_compatibility": "UNKNOWN",
        "owner_semantic_approval": "NOT_ADOPTED",
        "glossary_policy": "NOT_ADOPTED",
        "semantic_fp_fn": "NOT_EVALUATED",
        "rename_authorized": False,
    }
