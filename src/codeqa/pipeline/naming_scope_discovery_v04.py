"""Read-only, exhaustive *pinned Git tree* coverage for #144 spellings.

An exact tree manifest enumerates every tracked src/codeqa/**/*.py at an
immutable commit. Every blob must be checked; missing paths are not absence.
This records AST sites but never proposes an approved business/domain role.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from hashlib import sha1, sha256
from pathlib import Path
import re
import subprocess
from typing import Any

from codeqa.core.naming_scope_discovery_v04 import (
    ScopeDiscoveryError, scan_explicit_spellings,
)
from codeqa.infrastructure.git import GitReader

_SHA40 = re.compile(r"[0-9a-f]{40}\Z")
_TARGETS = ("time_step", "timestep", "node_id", "nodeid")
_EXPECTED_KEYS = {
    "schema_version", "repo", "source_commit", "source_tree_sha",
    "selection", "target_spellings", "observed_semantics",
    "applied_role_scopes", "glob_policy", "files", "coverage_claim",
    "automatic_rename_authorized",
}


class ScopeEvidenceError(ValueError):
    """Incomplete tracked corpus, mismatched bytes or untrusted policy claims."""


def _git(root: Path, *args: str) -> bytes:
    result = subprocess.run(("git", *args), cwd=root, capture_output=True,
                            check=False, timeout=25)
    if result.returncode != 0:
        raise ScopeEvidenceError("cannot verify immutable Git tree")
    return result.stdout


def _tree_manifest(root: Path, commit: str) -> tuple[str, dict[str, str]]:
    tree = _git(root, "rev-parse", f"{commit}^{{tree}}").decode("ascii").strip()
    if not _SHA40.fullmatch(tree):
        raise ScopeEvidenceError("invalid pinned Git tree identity")
    result = _git(root, "ls-tree", "-r", "-z", commit, "--", "src/codeqa")
    selected: dict[str, str] = {}
    for entry in result.split(b"\0"):
        if not entry:
            continue
        try:
            metadata, path_bytes = entry.split(b"\t", 1)
            mode, objkind, digest = metadata.decode("ascii").split(" ")
            path = path_bytes.decode("utf-8")
        except (ValueError, UnicodeDecodeError) as exc:
            raise ScopeEvidenceError("invalid Git tree entry") from exc
        if path.startswith("src/codeqa/") and path.endswith(".py"):
            if (objkind != "blob" or mode not in ("100644", "100755")
                    or not _SHA40.fullmatch(digest) or path in selected):
                raise ScopeEvidenceError("unsupported/duplicate selected Git path")
            selected[path] = digest
    if not selected:
        raise ScopeEvidenceError("no selected Python source in pinned Git tree")
    return tree, selected


def discover_pinned_semantic_scope(
    root: Path, manifest: Mapping[str, Any],
) -> dict[str, Any]:
    """Fail closed on manifest omissions, stale Git blobs or parse failures.

    The repo-local GitReader supplies actual historical bytes, never worktree
    content. Caller-reported owner/role is not sufficient to adopt a policy.
    """
    if (not isinstance(manifest, Mapping) or set(manifest) != _EXPECTED_KEYS
            or manifest["schema_version"] != "0.4-source-scope-discovery"
            or manifest["repo"] != "HyungseonSong-plasma/codeQA"
            or manifest["selection"] != "src/codeqa/**/*.py"
            or manifest["target_spellings"] != list(_TARGETS)
            or manifest["observed_semantics"] != "NOT_EVALUATED"
            or manifest["applied_role_scopes"] != []
            or manifest["glob_policy"] != "TRACKED_GIT_TREE_EXACT_PATHS"
            or manifest["coverage_claim"] != "PINNED_TRACKED_PYTHON_PATHS_ONLY"
            or manifest["automatic_rename_authorized"] is not False):
        raise ScopeEvidenceError("unapproved or malformed source-scope manifest")
    pin = manifest["source_commit"]
    expected_tree = manifest["source_tree_sha"]
    if (not isinstance(pin, str) or not _SHA40.fullmatch(pin)
            or not isinstance(expected_tree, str)
            or not _SHA40.fullmatch(expected_tree)):
        raise ScopeEvidenceError("full source commit and Git tree pins required")
    root = Path(root).resolve()
    verified_tree, selected = _tree_manifest(root, pin)
    if expected_tree != verified_tree:
        raise ScopeEvidenceError("Git tree commit/source identity drift")
    files = manifest["files"]
    if not isinstance(files, list) or not files:
        raise ScopeEvidenceError("complete tracked Python file list required")
    alleged: dict[str, str] = {}
    for f in files:
        if (not isinstance(f, dict) or set(f) != {"path", "git_blob_sha"}
                or not isinstance(f["path"], str)
                or not f["path"].startswith("src/codeqa/")
                or not f["path"].endswith(".py")
                or ".." in f["path"].split("/")
                or not isinstance(f["git_blob_sha"], str)
                or not _SHA40.fullmatch(f["git_blob_sha"])
                or f["path"] in alleged):
            raise ScopeEvidenceError("duplicate, escaped or malformed tracked path")
        alleged[f["path"]] = f["git_blob_sha"]
    if alleged != selected:
        raise ScopeEvidenceError("pinned Git tree denominator or blob set mismatch")

    reader = GitReader(root)
    source_files = []
    results: list[dict[str, object]] = []
    for path in sorted(selected):
        data = reader.read_file(pin, path)
        actual_blob = sha1(b"blob " + str(len(data)).encode("ascii")
                           + b"\0" + data).hexdigest()
        if actual_blob != selected[path]:
            raise ScopeEvidenceError("byte read does not match pinned tree blob")
        try:
            observed = scan_explicit_spellings(
                data, path=path, targets=_TARGETS)
        except ScopeDiscoveryError as exc:
            raise ScopeEvidenceError("invalid selected source: " + path) from exc
        source_files.append({
            "path": path, "git_blob_sha": actual_blob,
            "source_sha256": sha256(data).hexdigest(),
            "ast_parse": "PASS",
        })
        results.extend(observed)

    counts = Counter(r["source_kind"] for r in results)
    declarations = {
        "function", "method", "parameter", "class_annotation",
        "class_binding", "module_binding", "local_binding", "class",
    }
    candidates = [r for r in results if r["source_kind"] in declarations]
    return {
        "schema_version": "0.4-pinned-semantic-scope-evidence",
        "repo": manifest["repo"],
        "source_commit": pin,
        "source_tree_sha": verified_tree,
        "requested_spellings": list(_TARGETS),
        "selected_source_file_count": len(selected),
        "files_scanned": len(source_files),
        "ast_parsed_file_count": len(source_files),
        "file_evidence": source_files,
        "exact_ast_spelling_count": len(results),
        "site_kind_counts": dict(sorted(counts.items())),
        "unresolved_binding_reference_count": sum(
            n for k, n in counts.items() if k in (
                "attribute_unresolved", "name_reference_unresolved", "import_alias")),
        "structural_declaration_candidate_count": len(candidates),
        "lexical_site_evidence": results,
        "proposed_path_role_scopes": [{
            "path": r["path"], "kind": r["source_kind"],
            "source_name": r["name"], "source_line": r["line"],
            "lexical_owner": r["owner"],
            "role": "UNKNOWN", "role_evidence": "NOT_EVALUATED",
            "approved_scope": False,
        } for r in candidates],
        "policy_adoption": "NOT_ADOPTED",
        "semantic_meaning": "NOT_EVALUATED",
        "source_reference_completeness": "NOT_EVALUATED",
        "external_api_compatibility": "NOT_EVALUATED",
        "automatic_rename_authorized": False,
        "source_observation_gate": "PASS",
        "semantic_policy_gate": "UNKNOWN",
    }
