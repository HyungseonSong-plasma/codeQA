"""Manual, opt-in Rust naming witness evaluation (#72).

Never claim parser, trait binding, compiler or runtime verification.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from collections.abc import Mapping
import re


class RustManualEvidenceError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class RustManualObservation:
    name: str
    kind: str
    line: int
    status: str
    reason: str


@dataclass(frozen=True, slots=True)
class RustManualReport:
    schema_version: str
    profile_id: str
    source_sha256: str
    observations: tuple[RustManualObservation, ...]
    parser_status: str = "NOT_EVALUATED"
    compiler_status: str = "NOT_EVALUATED"
    trait_resolution_status: str = "NOT_EVALUATED"
    source_revision_status: str = "NOT_EVALUATED"
    runtime_approved: bool = False


_SNAKE = re.compile(r"[a-z][a-z0-9]*(?:_[a-z0-9]+)*\Z")
_PASCAL = re.compile(r"[A-Z][a-zA-Z0-9]*\Z")
_UPPER = re.compile(r"[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)*\Z")
_STYLES = {"snake_case": _SNAKE, "PascalCase": _PASCAL,
           "UPPER_SNAKE_CASE": _UPPER}
_CONTEXTS = frozenset({
    "declaration", "inherent", "trait_required", "trait_impl",
    "external_reexport", "macro_definition", "macro_invocation",
    "raw_identifier", "lifetime", "generated",
})


def assess_manual_rust_naming(
    profile: Mapping[str, object], manifest: Mapping[str, object], source: str,
) -> RustManualReport:
    if not isinstance(profile, Mapping) or not isinstance(manifest, Mapping):
        raise RustManualEvidenceError("typed explicit profile and manifest required")
    if not isinstance(source, str):
        raise RustManualEvidenceError("source must be UTF-8 text")
    if (profile.get("schema_version") != "0.2-draft"
            or profile.get("mode") != "manual_curated_fixture"
            or manifest.get("schema_version") != "0.2-draft"
            or manifest.get("producer") != "manual_curated_fixture"):
        raise RustManualEvidenceError("only explicit v0.2 manual fixture is supported")
    for obj in (profile, manifest):
        for key in ("parser_status", "compiler_status", "trait_resolution_status"):
            if obj.get(key) != "NOT_EVALUATED":
                raise RustManualEvidenceError("forged parser/compiler/trait result")
    if manifest.get("source_revision_status") != "NOT_EVALUATED":
        raise RustManualEvidenceError("manual fixture is not a verified Git revision")
    if manifest.get("scope") != "synthetic_fixture_only":
        raise RustManualEvidenceError("manual specimen cannot attest broader source scope")
    if not isinstance(profile.get("profile_id"), str) or not profile["profile_id"]:
        raise RustManualEvidenceError("versioned profile id required")
    digest = sha256(source.encode("utf-8")).hexdigest()
    if manifest.get("source_sha256") != digest:
        raise RustManualEvidenceError("synthetic specimen digest drift")
    rules = profile.get("rules")
    if not isinstance(rules, Mapping) or not isinstance(manifest.get("witnesses"), list):
        raise RustManualEvidenceError("rules and witnesses required")
    if any(rule not in _STYLES for rule in rules.values()):
        raise RustManualEvidenceError("unrecognized naming style")
    lines = source.splitlines()
    observed: list[RustManualObservation] = []
    seen: set[tuple[str, str, int, str]] = set()
    for raw in manifest["witnesses"]:
        if not isinstance(raw, Mapping) or set(raw) != {"name", "kind", "line", "context"}:
            raise RustManualEvidenceError("invalid witness shape")
        name, kind, line, context = (raw[x] for x in ("name", "kind", "line", "context"))
        if (not isinstance(name, str) or not name or not isinstance(kind, str)
                or not isinstance(context, str) or context not in _CONTEXTS
                or not isinstance(line, int) or isinstance(line, bool)
                or line < 1 or line > len(lines)):
            raise RustManualEvidenceError("invalid source location")
        identity = (name, kind, line, context)
        if identity in seen:
            raise RustManualEvidenceError("ambiguous duplicate manual witness")
        seen.add(identity)
        if not re.search(r"(?<![A-Za-z0-9_#])" + re.escape(name)
                         + r"(?![A-Za-z0-9_])", lines[line - 1]):
            raise RustManualEvidenceError("witness does not occur at declared source line")
        if kind not in rules:
            observed.append(RustManualObservation(
                name, kind, line, "NOT_EVALUATED", "unsupported identifier category"))
            continue
        if context in {"trait_required", "trait_impl", "external_reexport",
                       "macro_definition", "macro_invocation", "generated",
                       "raw_identifier"} or not name.isascii():
            observed.append(RustManualObservation(
                name, kind, line, "NOT_EVALUATED",
                "requires parser, trait or external framework evidence"))
            continue
        matches = bool(_STYLES[rules[kind]].fullmatch(name))
        observed.append(RustManualObservation(
            name, kind, line,
            "STYLE_MATCH_CANDIDATE" if matches else "STYLE_REVIEW_CANDIDATE",
            "lexical witness only; not compiler/trait proof"))
    return RustManualReport(
        "0.2-draft", profile["profile_id"], digest, tuple(observed))
