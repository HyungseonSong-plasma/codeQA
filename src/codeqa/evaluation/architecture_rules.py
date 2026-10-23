"""Versioned policy facade over the existing semantic_layout evaluator.

The *old* evaluate_semantic_layout remains the single authority for forbidden
source-role edges, missing roles and exact transition exceptions. This facade
adds dated policy validation, grounded AST import statements, uncertainty and
coverage without manufacturing runtime dependency or P4/P5 assurance.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import date
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from codeqa.core import Graph
from codeqa.core.dependency import DependencyGraph
from codeqa.evaluation.semantic_layout import evaluate_semantic_layout


class DeclaredRuleError(ValueError):
    """Unverifiable source policy identity, dates or contradictory role map."""


def _day(value: str) -> date:
    try:
        parsed = date.fromisoformat(value)
        if parsed.isoformat() != value:
            raise ValueError("non-canonical date")
        return parsed
    except (ValueError, TypeError) as exc:
        raise DeclaredRuleError("invalid canonical ISO calendar day") from exc


def _path(value: str) -> bool:
    return (
        isinstance(value, str) and bool(value)
        and not value.startswith("/") and "\\" not in value and "\x00" not in value
        and not (len(value) >= 2 and value[0].isalpha() and value[1] == ":")
        and all(part not in ("", ".", "..") for part in value.split("/"))
    )


def validate_declared_rule_policy(
    policy: Mapping[str, Any], schema: Mapping[str, Any],
) -> dict[str, Any]:
    Draft202012Validator.check_schema(schema)
    errors = sorted(
        Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(policy),
        key=lambda error: (str(list(error.absolute_path)), error.message),
    )
    if errors:
        raise DeclaredRuleError("invalid policy shape: " + errors[0].message)
    _day(policy["effective_from"])
    root = policy["scope"]
    if not _path(root):
        raise DeclaredRuleError("unsafe policy scope")
    roles = policy["roles"]
    keys = set(roles)
    for name, definition in roles.items():
        if not _path(name) or "/" in name:
            raise DeclaredRuleError("unsafe declared directory role")
        allowed = set(definition["allowed_imports"])
        denied = set(definition["forbidden_imports"])
        if allowed & denied or (allowed | denied) != keys:
            raise DeclaredRuleError("role dependency directions must partition all declared roles")
    ids = set()
    pairs = set()
    for exception in policy["exceptions"]:
        until = _day(exception["expires_on"])
        if (not _path(exception["source"]) or not _path(exception["target"])
                or not exception["source"].startswith(root + "/")
                or not exception["target"].startswith(root + "/")):
            raise DeclaredRuleError("invalid source/target exception scope")
        src = exception["source"][len(root) + 1:].split("/")[0]
        dst = exception["target"][len(root) + 1:].split("/")[0]
        if src not in roles or dst not in roles[src]["forbidden_imports"]:
            raise DeclaredRuleError("exception cannot authorize unprohibited direction")
        pair = (exception["source"], exception["target"])
        if exception["id"] in ids or pair in pairs:
            raise DeclaredRuleError("duplicate exception ID/source-target identity")
        if until < _day(policy["effective_from"]):
            raise DeclaredRuleError("exception expires before effective policy date")
        ids.add(exception["id"])
        pairs.add(pair)
    return dict(policy)


@dataclass(frozen=True, slots=True)
class DeclaredRuleFinding:
    rule_id: str
    policy_clause: str
    status: str
    code: str
    source: str
    target: str | None
    line: int | None
    expression: str | None
    execution: str | None
    reason: str
    exception_id: str | None = None


@dataclass(frozen=True, slots=True)
class DeclaredRuleReport:
    snapshot_id: str
    policy_id: str
    revision: str
    as_of: str
    scope: str
    coverage_status: str
    unprocessed_paths: tuple[str, ...]
    findings: tuple[DeclaredRuleFinding, ...]
    status: str
    schema_version: str = "0.1"
    interpretation: str = "DECLARED_STATIC_POLICY_ONLY_NOT_P4_P5_CERTIFICATION"

    def to_document(self) -> dict[str, Any]:
        def json_value(value: Any) -> Any:
            if isinstance(value, (list, tuple)):
                return [json_value(item) for item in value]
            if isinstance(value, dict):
                return {key: json_value(item) for key, item in value.items()}
            return value
        return json_value(asdict(self))


def evaluate_declared_architecture_rules(
    graph: Graph,
    dependencies: DependencyGraph,
    policy: Mapping[str, Any],
    *,
    schema: Mapping[str, Any],
    source_as_of: str,
) -> DeclaredRuleReport:
    """Evaluate only declared, source-grounded *static* role constraints."""
    if not isinstance(graph, Graph) or not isinstance(dependencies, DependencyGraph):
        raise TypeError("expected validated CCG and DependencyGraph")
    declared = validate_declared_rule_policy(policy, schema)
    as_of = _day(source_as_of)
    if graph.snapshot.id != dependencies.snapshot_id:
        raise DeclaredRuleError("CCG and dependency snapshot identities disagree")
    selected = set(graph.coverage.analyzed_paths)
    if (set(dependencies.analyzed_paths) != selected or
            set(dependencies.unprocessed_paths) != {
                item.path for item in graph.coverage.unprocessed
            }):
        raise DeclaredRuleError("dependency file coverage contradicts CCG")
    for edge in dependencies.edges:
        if (edge.source_path not in selected or edge.target_path not in selected
                or type(edge.line) is not int or edge.line < 1 or not edge.expression
                or edge.execution not in ("top_level", "conditional_or_deferred")):
            raise DeclaredRuleError("dependency edge has no bounded source witness")
    for unknown in dependencies.unknown:
        if (unknown.source_path not in selected or type(unknown.line) is not int
                or unknown.line < 1 or not unknown.reason or not unknown.expression):
            raise DeclaredRuleError("unknown dependency observation is ungrounded")

    findings: list[DeclaredRuleFinding] = []
    def add(rule_id: str, clause: str, status: str, code: str,
            src: str, dst: str | None, reason: str,
            *, line: int | None = None, expression: str | None = None,
            execution: str | None = None, exception_id: str | None = None) -> None:
        findings.append(DeclaredRuleFinding(
            rule_id, clause, status, code, src, dst, line, expression,
            execution, reason, exception_id,
        ))

    root = declared["scope"]
    if as_of < _day(declared["effective_from"]) or declared["temporality"] == "RETROSPECTIVE":
        add("policy:temporal_scope", "effective_from", "NOT_EVALUATED",
            "RETROSPECTIVE_OR_INAPPLICABLE_POLICY", root, None,
            "caller source date predates policy or only retrospective mapping is declared")
    elif graph.coverage.status != "complete":
        add("coverage:complete", "source_coverage", "NOT_EVALUATED",
            "PARTIAL_SOURCE_COVERAGE", root, None,
            "selected input has unprocessed source; cannot certify role absence")
    else:
        active = []
        expired = {}
        for item in declared["exceptions"]:
            pair = (item["source"], item["target"])
            if _day(item["expires_on"]) >= as_of:
                active.append({
                    "source": item["source"], "target": item["target"],
                    "status": "TRANSITIONAL_REVIEW", "rationale": item["rationale"],
                })
            else:
                expired[pair] = item

        # The established role evaluator is authoritative. We only attach
        # precise source-line witnesses and versioned policy clauses.
        old_policy = {
            "policy_id": declared["policy_id"], "scope": root,
            "roles": {
                key: {
                    "responsibility": data["responsibility"],
                    "forbidden_imports": data["forbidden_imports"],
                } for key, data in declared["roles"].items()
            }, "exceptions": active,
        }
        underlying = evaluate_semantic_layout(
            graph.coverage.analyzed_paths,
            ((e.source_path, e.target_path) for e in dependencies.edges),
            old_policy,
        )
        witnesses: dict[tuple[str, str], list] = {}
        for edge in dependencies.edges:
            witnesses.setdefault((edge.source_path, edge.target_path), []).append(edge)
        for finding in underlying.findings:
            pairs = witnesses.get((finding.source, finding.target or ""), ())
            if finding.code == "FORBIDDEN_ROLE_DEPENDENCY" or (
                finding.code == "DECLARED_TRANSITIONAL_EDGE"
            ):
                role = finding.source[len(root)+1:].split("/")[0]
                target = finding.target[len(root)+1:].split("/")[0]
                rule = f"direction:{role}->{target}"
                for edge in sorted(pairs, key=lambda x: (x.line, x.expression)):
                    exception = next(
                        (x for x in active if x["source"] == edge.source_path
                         and x["target"] == edge.target_path), None,
                    )
                    exception_id = next(
                        (x["id"] for x in declared["exceptions"]
                         if x["source"] == edge.source_path
                         and x["target"] == edge.target_path), None,
                    ) if exception is not None else None
                    add(rule, "roles." + role + ".forbidden_imports",
                        finding.status, finding.code,
                        finding.source, finding.target, finding.reason,
                        line=edge.line, expression=edge.expression,
                        execution=edge.execution, exception_id=exception_id)
            elif finding.code == "MISSING_DECLARED_ROLE" and not declared["scope_inventory_complete"]:
                add("coverage:declared_role_present", "scope_inventory_complete",
                    "NOT_EVALUATED", "ROLE_ABSENCE_UNPROVEN",
                    finding.source, None,
                    "caller has not attested that all paths in scope were inventoried")
            else:
                add("policy:" + finding.code.lower(), "declared_roles",
                    finding.status, finding.code, finding.source,
                    finding.target, finding.reason)
        for pair, exception in sorted(expired.items()):
            add("exception:" + exception["id"], "exceptions.expires_on",
                "REVIEW_REQUIRED", "EXPIRED_EXCEPTION",
                exception["source"], exception["target"],
                "expired exception cannot authorize forbidden imports",
                exception_id=exception["id"])

    # Unresolved/dynamic dependencies remain visible, never counted as clean.
    for item in dependencies.unknown:
        add("coverage:unknown_dependency", "static_import_resolution",
            "NOT_EVALUATED", "UNKNOWN_STATIC_IMPORT_TARGET",
            item.source_path, None, item.reason, line=item.line,
            expression=item.expression)
    statuses = {f.status for f in findings}
    status = ("VIOLATION" if "VIOLATION" in statuses else
              "REVIEW_REQUIRED" if "REVIEW_REQUIRED" in statuses else "NOT_EVALUATED")
    findings.sort(key=lambda x: (
        x.status, x.code, x.rule_id, x.source, x.target or "",
        x.line or 0, x.expression or "",
    ))
    return DeclaredRuleReport(
        snapshot_id=graph.snapshot.id,
        policy_id=declared["policy_id"], revision=declared["revision"],
        as_of=source_as_of, scope=root,
        coverage_status=graph.coverage.status,
        unprocessed_paths=tuple(sorted(u.path for u in graph.coverage.unprocessed)),
        findings=tuple(findings), status=status,
    )
