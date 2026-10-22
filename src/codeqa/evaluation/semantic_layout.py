"""Repository-neutral semantic directory-role assessment, evidence-led.

A declared role is NOT verified solely from directory spelling. This evaluator
can prove an explicit forbidden import edge, missing declared roles and
unclassified folders. It never guesses whether a function's implementation
matches its human-language responsibility. Transitional exceptions remain
review findings rather than falsely reporting ALIGNED.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable, Mapping


@dataclass(frozen=True, slots=True)
class SemanticLayoutFinding:
    status: str  # VIOLATION | REVIEW_REQUIRED | NOT_EVALUATED
    code: str
    source: str
    target: str | None
    reason: str


@dataclass(frozen=True, slots=True)
class SemanticLayoutReport:
    policy_id: str
    evaluated_roles: tuple[str, ...]
    findings: tuple[SemanticLayoutFinding, ...]
    status: str

    def to_document(self) -> dict[str, Any]:
        return asdict(self)


def _path(value: Any) -> bool:
    return (
        isinstance(value, str) and bool(value)
        and not value.startswith("/") and "\\" not in value and "\x00" not in value
        and all(part not in ("", ".", "..") for part in value.split("/"))
    )


def _validate(policy: Mapping[str, Any]) -> tuple[str, dict, dict]:
    if not isinstance(policy, Mapping):
        raise ValueError("semantic role policy must be a mapping")
    root = policy.get("scope")
    roles = policy.get("roles")
    exceptions = policy.get("exceptions")
    if not _path(root) or not isinstance(roles, dict) or not roles:
        raise ValueError("scope and nonempty roles required")
    if not isinstance(exceptions, list):
        raise ValueError("exceptions must be a list")
    for role, definition in roles.items():
        if not _path(role) or "/" in role or not isinstance(definition, dict):
            raise ValueError("invalid role")
        prohibited = definition.get("forbidden_imports")
        if not isinstance(definition.get("responsibility"), str) or not definition["responsibility"]:
            raise ValueError("each role needs a written responsibility")
        if not isinstance(prohibited, list) or len(set(prohibited)) != len(prohibited):
            raise ValueError("forbidden imports must be unique role names")
        if any(name not in roles for name in prohibited):
            raise ValueError("forbidden imports must name declared roles")
    approved = {}
    for item in exceptions:
        if not isinstance(item, dict):
            raise ValueError("exceptions must be objects")
        src, dst = item.get("source"), item.get("target")
        if not _path(src) or not _path(dst) or not src.startswith(root + "/") or not dst.startswith(root + "/"):
            raise ValueError("exceptions must be paths within role scope")
        sr, dr = src[len(root)+1:].split("/")[0], dst[len(root)+1:].split("/")[0]
        if sr not in roles or dr not in roles[sr]["forbidden_imports"]:
            raise ValueError("exception must cover a genuinely forbidden role edge")
        if item.get("status") != "TRANSITIONAL_REVIEW" or not item.get("rationale"):
            raise ValueError("exceptions require transitional review and rationale")
        if (src, dst) in approved:
            raise ValueError("duplicate exception")
        approved[(src, dst)] = item["rationale"]
    return root, roles, approved


def evaluate_semantic_layout(
    paths: Iterable[str],
    import_pairs: Iterable[tuple[str, str]],
    policy: Mapping[str, Any],
) -> SemanticLayoutReport:
    """Evaluate declared paths and exact module-path import correspondence.

    Missing correspondence is not evidence of absence of dependencies.
    Other semantics (contents, naming conformance, runtime dispatch) remain
    NOT_EVALUATED; this does not produce a general semantic alignment PASS.
    """
    root, roles, approved = _validate(policy)
    scoped: set[str] = set()
    for path in paths:
        if not _path(path):
            raise ValueError("invalid tracked path")
        if path.startswith(root + "/"):
            scoped.add(path)
    findings: set[SemanticLayoutFinding] = set()
    present = {
        p[len(root)+1:].split("/")[0] for p in scoped
    }
    for role in sorted(roles):
        if role not in present:
            findings.add(SemanticLayoutFinding(
                "VIOLATION", "MISSING_DECLARED_ROLE", root + "/" + role, None,
                "declared directory has no tracked source files",
            ))
    for role in sorted(present - set(roles)):
        findings.add(SemanticLayoutFinding(
            "NOT_EVALUATED", "UNCLASSIFIED_ROLE", root + "/" + role, None,
            "no declared responsibility; cannot judge this folder",
        ))
    seen: set[tuple[str, str]] = set()
    for src, dst in import_pairs:
        if not _path(src) or not _path(dst):
            raise ValueError("invalid import path")
        if (src, dst) in seen:
            continue
        seen.add((src, dst))
        if not src.startswith(root + "/") or not dst.startswith(root + "/"):
            continue
        sr, dr = src[len(root)+1:].split("/")[0], dst[len(root)+1:].split("/")[0]
        if sr not in roles or dr not in roles:
            continue
        if dr not in roles[sr]["forbidden_imports"]:
            continue
        rationale = approved.get((src, dst))
        if rationale is not None:
            findings.add(SemanticLayoutFinding(
                "REVIEW_REQUIRED", "DECLARED_TRANSITIONAL_EDGE", src, dst, rationale,
            ))
        else:
            findings.add(SemanticLayoutFinding(
                "VIOLATION", "FORBIDDEN_ROLE_DEPENDENCY", src, dst,
                f"role {sr!r} must not import role {dr!r}",
            ))
    # A declared exception must not silently become dead governance debt.
    for src, dst in sorted(approved):
        if (src, dst) not in seen:
            findings.add(SemanticLayoutFinding(
                "REVIEW_REQUIRED", "EXCEPTION_NOT_OBSERVED", src, dst,
                "retire or correct obsolete transitional exception",
            ))
    ordered = tuple(sorted(findings, key=lambda x: (
        x.status, x.code, x.source, x.target or "",
    )))
    severity = {f.status for f in ordered}
    status = "VIOLATION" if "VIOLATION" in severity else (
        "REVIEW_REQUIRED" if "REVIEW_REQUIRED" in severity else
        "NOT_EVALUATED"
    )
    return SemanticLayoutReport(
        policy_id=str(policy.get("policy_id", "unversioned")),
        evaluated_roles=tuple(sorted(roles)),
        findings=ordered,
        status=status,
    )
