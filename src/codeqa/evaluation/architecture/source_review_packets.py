"""Exact-source snippets for human review of B8's measured cross-role edges.

Evidence packets do not classify ownership, move files, or seed discovery.
"""
from __future__ import annotations

import ast
from collections.abc import Mapping
from hashlib import sha256
import json
from typing import Any


class SourceReviewPacketError(ValueError):
    """A review packet cannot be tied to its immutable source and worklist."""


def _digest(value: Any) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


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
        imports_by_path: dict[str, set[int]] = {}
        hashes: dict[str, str] = {}
        for path in sorted(expected_paths):
            raw = source_blobs[path]
            if not isinstance(raw, bytes):
                raise SourceReviewPacketError("source must be exact Git bytes")
            hashes[path] = sha256(raw).hexdigest()
            lines_by_path[path] = raw.decode("utf-8").splitlines()
            tree = ast.parse(raw, filename=path)
            imports_by_path[path] = {
                node.lineno for node in ast.walk(tree)
                if isinstance(node, (ast.Import, ast.ImportFrom))
            }

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
            for witness in row["import_witnesses"]:
                line = witness["line"]
                if (witness["source_path"] != src
                        or witness["target_path"] != dst
                        or witness["source_sha256"] != hashes[src]
                        or type(line) is not int
                        or line not in imports_by_path[src]):
                    raise SourceReviewPacketError("unbound import witness")
                imports.append(excerpt(src, line))
            calls = [excerpt(src, w["caller_line"])
                     for w in row["callsite_examples"]]
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
                "source snippets do not prove intentional composition or misplaced ownership",
                "test-path candidates do not prove behavioral edge coverage",
                "external consumers and public API compatibility require separate review",
            ],
        }
        result["packets_id"] = _digest(result)
        return result
    except (KeyError, TypeError, ValueError, UnicodeError, SyntaxError, AttributeError) as exc:
        raise SourceReviewPacketError("untrustworthy source review packet evidence") from exc


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
