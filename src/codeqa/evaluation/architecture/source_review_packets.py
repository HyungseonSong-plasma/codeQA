"""Exact-source snippets for human review of B8's measured cross-role edges.

Evidence packets do not classify ownership, move files, or seed discovery.
"""
from __future__ import annotations

import ast
from collections.abc import Mapping
from hashlib import sha256
import json
from typing import Any

from codeqa.evaluation.architecture.callsite_context import _function_context


class SourceReviewPacketError(ValueError):
    """A review packet cannot be tied to its immutable source and worklist."""


def _digest(value: Any) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()



def _module_name(path: str) -> tuple[str, bool]:
    """Match the snapshot-local Python dependency adapter's module naming rule."""
    if not isinstance(path, str) or not path.endswith(".py"):
        raise SourceReviewPacketError("unindexable Python module path")
    relative = path.removeprefix("src/") if path.startswith("src/") else path
    parts = relative.removesuffix(".py").split("/")
    package = parts[-1] == "__init__"
    if package:
        parts.pop()
    if not parts or any(not part.isidentifier() for part in parts):
        raise SourceReviewPacketError("unindexable Python module path")
    return ".".join(parts), package


def _observed_imports(path: str, tree: ast.Module) -> dict[int, list[tuple[set[str], str, str]]]:
    """Resolve only the module named by each import, never guessed members.

    This mirrors the dependency adapter's syntax rule. It does not prove that
    the import completed or that the target path is unique in the snapshot.
    """
    module, package = _module_name(path)
    direct = {id(node) for node in tree.body}
    result: dict[int, list[tuple[set[str], str, str]]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            # The dependency adapter records one edge per alias and stores
            # "import <module>" rather than the entire aliased statement.
            candidates = [({alias.name}, "import " + alias.name)
                          for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                scope = module.split(".") if package else module.split(".")[:-1]
                if node.level > len(scope):
                    continue
                prefix = scope[:len(scope) - (node.level - 1)]
                targets = {".".join([*prefix, *([node.module] if node.module else [])])}
            else:
                targets = {node.module or ""}
            candidates = [(targets, ast.unparse(node))]
        else:
            continue
        for targets, expression in candidates:
            result.setdefault(node.lineno, []).append((
                targets, expression,
                "top_level" if id(node) in direct else "conditional_or_deferred",
            ))
    return result


def build_source_review_packets(
    worklist: Mapping[str, Any], source_blobs: Mapping[str, bytes],
) -> dict[str, Any]:
    """Bind every measured review row to exact Git bytes and source context.

    The caller reads blobs from the worklist's exact Git HEAD. Import lines,
    source SHA-256 and bounded caller snippets are rechecked here.
    """
    try:
        if (worklist["schema_version"] != "0.1"
                or worklist["worklist_id"] != _digest({
                    k: v for k, v in worklist.items() if k != "worklist_id"
                })
                or worklist["decision"] != "NOT_EVALUATED"
                or worklist["semantic_ownership"] != "NOT_EVALUATED"
                or worklist["recommended_action"] != "NO_AUTOMATIC_MOVE"
                or type(worklist["observed_cross_role_pairs"]) is not int
                or len(worklist["edges"]) != worklist["observed_cross_role_pairs"]
                or not isinstance(source_blobs, Mapping)):
            raise SourceReviewPacketError("untrusted source review scope")
        rows = worklist["edges"]
        expected_paths = {row["source_path"] for row in rows}
        if set(source_blobs) != expected_paths:
            raise SourceReviewPacketError("missing or unexpected source blob")
        lines_by_path: dict[str, list[str]] = {}
        trees_by_path: dict[str, ast.Module] = {}
        imports_by_path: dict[str, dict[int, list[tuple[set[str], str, str]]]] = {}
        hashes: dict[str, str] = {}
        for path in sorted(expected_paths):
            raw = source_blobs[path]
            if not isinstance(raw, bytes):
                raise SourceReviewPacketError("source must be exact Git bytes")
            hashes[path] = sha256(raw).hexdigest()
            lines_by_path[path] = raw.decode("utf-8").splitlines()
            tree = ast.parse(raw, filename=path)
            trees_by_path[path] = tree
            imports_by_path[path] = _observed_imports(path, tree)

        def excerpt(path: str, line: int) -> dict[str, Any]:
            lines = lines_by_path[path]
            if type(line) is not int or not 1 <= line <= len(lines):
                raise SourceReviewPacketError("witness outside source")
            start, end = max(1, line - 2), min(len(lines), line + 2)
            return {
                "witness_line": line,
                "source_sha256": hashes[path],
                "lines": [{"line": i, "text": lines[i - 1]}
                          for i in range(start, end + 1)],
            }

        packets = []
        seen: set[tuple[str, str]] = set()
        for row in sorted(rows, key=lambda x: (x["source_path"], x["target_path"])):
            src, dst = row["source_path"], row["target_path"]
            if (src, dst) in seen or not row["import_witnesses"]:
                raise SourceReviewPacketError("duplicate or unwitnessed edge")
            seen.add((src, dst))
            imports = []
            target_module, _ = _module_name(dst)
            for witness in row["import_witnesses"]:
                line = witness["line"]
                if (witness["source_path"] != src
                        or witness["target_path"] != dst
                        or witness["source_sha256"] != hashes[src]
                        or type(line) is not int
                        or not any(
                            target_module in modules
                            and witness["expression"] == expression
                            and witness["execution"] == execution
                            for modules, expression, execution
                            in imports_by_path[src].get(line, ())
                        )):
                    raise SourceReviewPacketError("import line does not bind measured target")
                imports.append(excerpt(src, line))
            # Caller frames can be implicit calls without an ast.Call node.
            # Validate only the lexical metadata previously measured by B8;
            # this never claims callee identity or runtime edge traversal.
            calls = []
            tree = trees_by_path[src]
            for witness in row["callsite_examples"]:
                line = witness["caller_line"]
                context = excerpt(src, line)
                statements = [
                    node for node in ast.walk(tree)
                    if isinstance(node, ast.stmt) and node.end_lineno is not None
                    and node.lineno <= line <= node.end_lineno
                ]
                statement = min(
                    statements,
                    key=lambda node: (node.end_lineno - node.lineno, -node.lineno),
                ) if statements else None
                kind = type(statement).__name__ if statement else None
                lexical = _function_context(tree, line)["function_qualname"]
                if (not isinstance(witness["test_id"], str)
                        or not witness["test_id"]
                        or witness["function_qualname"] != lexical
                        or witness["enclosing_statement_kind"] != kind):
                    raise SourceReviewPacketError("callsite lexical context mismatch")
                calls.append(context)
            if (row["semantic_ownership"] != "NOT_EVALUATED"
                    or row["public_api_compatibility"] != "NOT_EVALUATED"
                    or row["recommended_action"] != "NO_AUTOMATIC_MOVE"):
                raise SourceReviewPacketError("unsupported semantic conclusion")
            packets.append({
                "source_path": src, "target_path": dst,
                "source_role": row["source_role"],
                "target_role": row["target_role"],
                "declared_policy_direction": row["declared_policy_direction"],
                "review_focus": row["review_focus"],
                "import_excerpts": imports,
                "sampled_callsite_excerpts": calls,
                "candidate_test_paths": row["candidate_test_paths"],
                "fixture_call_candidate_sites": row["fixture_call_candidate_sites"],
                "semantic_ownership": "NOT_EVALUATED",
                "public_api_compatibility": "NOT_EVALUATED",
                "review_status": "HUMAN_EVIDENCE_REQUIRED",
            })
        result = {
            "schema_version": "0.1",
            "source_identity": {
                "snapshot_sha": worklist["source_identity"]["snapshot_sha"],
                "worklist_id": worklist["worklist_id"],
            },
            "observed_cross_role_pairs": len(packets),
            "packets": packets,
            "decision": "NOT_EVALUATED",
            "recommended_action": "NO_AUTOMATIC_MOVE",
            "limitations": [
                "import and sampled callsite excerpts are syntax, not callee identity",
                "import module-name matches do not prove uniqueness, execution or imported member identity",
                "source snippets do not prove intentional composition or misplaced ownership",
                "test-path candidates do not prove behavioral edge coverage",
                "external consumers and public API compatibility require separate review",
            ],
        }
        result["packets_id"] = _digest(result)
        return result
    except (KeyError, TypeError, ValueError, UnicodeError, SyntaxError, AttributeError) as exc:
        raise SourceReviewPacketError("untrustworthy source review packet evidence") from exc


def _validate_rendered_packet_rows(report: Mapping[str, Any]) -> None:
    """Reject resealed semantic promotion and internally inconsistent excerpts.

    The digest is an accidental-tamper guard, not an authentication signature.
    Exact source authenticity remains the responsibility of the builder and
    the B8 manifest; rendering must not turn an edited packet into approval.
    """
    if report["schema_version"] != "0.1":
        raise SourceReviewPacketError("unsupported packet schema")
    seen: set[tuple[str, str]] = set()
    source_hashes: dict[str, str] = {}
    for row in report["packets"]:
        src, dst = row["source_path"], row["target_path"]
        if (not isinstance(src, str) or not isinstance(dst, str)
                or not src or not dst or src == dst
                or (src, dst) in seen
                or row["review_status"] != "HUMAN_EVIDENCE_REQUIRED"
                or row["semantic_ownership"] != "NOT_EVALUATED"
                or row["public_api_compatibility"] != "NOT_EVALUATED"
                or not row["import_excerpts"]):
            raise SourceReviewPacketError("unsupported packet review assertion")
        seen.add((src, dst))
        for excerpt in (*row["import_excerpts"], *row["sampled_callsite_excerpts"]):
            line = excerpt["witness_line"]
            digest = excerpt["source_sha256"]
            lines = excerpt["lines"]
            if (type(line) is not int or line < 1
                    or not isinstance(digest, str) or len(digest) != 64
                    or not isinstance(lines, list) or not lines
                    or any(type(item["line"]) is not int
                           or not isinstance(item["text"], str)
                           for item in lines)
                    or [item["line"] for item in lines]
                       != list(range(lines[0]["line"], lines[-1]["line"] + 1))
                    or line not in {item["line"] for item in lines}
                    or (src in source_hashes and source_hashes[src] != digest)):
                raise SourceReviewPacketError("inconsistent source excerpt")
            source_hashes[src] = digest


def render_source_review_packets_markdown(report: Mapping[str, Any]) -> str:
    """Render source excerpts without an implicit KEEP or move recommendation."""
    try:
        if (report["packets_id"] != _digest({
                k: v for k, v in report.items() if k != "packets_id"
            })
                or report["decision"] != "NOT_EVALUATED"
                or report["recommended_action"] != "NO_AUTOMATIC_MOVE"
                or report["observed_cross_role_pairs"] != len(report["packets"])):
            raise SourceReviewPacketError("modified source review packets")
        _validate_rendered_packet_rows(report)
        lines = [
            "## Source-linked responsibility review packets", "",
            "Exact source HEAD: " + report["source_identity"]["snapshot_sha"],
            "Observed pairs: " + str(report["observed_cross_role_pairs"]),
            "Evidence only; intentional composition and ownership leaks require review.",
        ]
        for row in report["packets"]:
            lines.extend([
                "", "- " + row["source_path"] + " -> " + row["target_path"]
                + " (" + row["source_role"] + " -> " + row["target_role"] + ")",
                "  - Focus: " + row["review_focus"] + "; " + row["review_status"],
            ])
            for kind, excerpts in (("Import", row["import_excerpts"]),
                                   ("Sampled caller", row["sampled_callsite_excerpts"])):
                for excerpt in excerpts:
                    lines.append("  - " + kind + " source line " + str(excerpt["witness_line"])
                                 + " sha256=" + excerpt["source_sha256"])
                    lines.extend("    - " + str(line["line"]) + ": " + line["text"]
                                 for line in excerpt["lines"])
            lines.append("  - Semantic ownership and public API: NOT_EVALUATED")
        if not report["packets"]:
            lines.append("- No measured concentration edges; no forced question.")
        lines.extend(["", "No package move or global KEEP/PASS follows from these excerpts.", ""])
        return "\n".join(lines)
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise SourceReviewPacketError("untrustworthy source review packet report") from exc
