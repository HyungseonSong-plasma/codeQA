"""Opt-in repeated direct statement review. Syntax similarity is not a clone verdict."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict,dataclass
import re
from typing import Any

from codeqa.core.statement_similarity import (
    StatementPatternEvidence,StatementPatternProfile,StatementSimilarityError,
    StatementWitness,
)


@dataclass(frozen=True,slots=True)
class RepeatedStatementGroup:
    owner_id: str
    statement_kind: str
    normalized_syntax_sha256: str
    witnesses: tuple[StatementWitness,...]


@dataclass(frozen=True,slots=True)
class StatementSimilarityReport:
    schema_version: str
    snapshot_id: str
    profile_id: str
    profile_fingerprint: str
    analyzed_paths: tuple[str,...]
    unprocessed: tuple[tuple[str,str],...]
    coverage_status: str
    eligible_direct_statements: int
    repeated_statement_occurrences: int
    groups: tuple[RepeatedStatementGroup,...]
    not_evaluated: tuple[str,...]
    status: str
    interpretation: str = "INTRA_FUNCTION_SYNTAX_PATTERN_NOT_BEHAVIOR_OR_AUTOMATIC_REFACTOR"

    def to_document(self)->dict[str,Any]:
        def conv(value:Any)->Any:
            if isinstance(value,(tuple,list)):
                return [conv(x) for x in value]
            if isinstance(value,dict):
                return {k:conv(v) for k,v in value.items()}
            return value
        return conv(asdict(self))


def evaluate_statement_similarity(
    evidence: StatementPatternEvidence,
    profile: StatementPatternProfile,
) -> StatementSimilarityReport:
    if not isinstance(evidence,StatementPatternEvidence):
        raise TypeError("source statement evidence required")
    if not isinstance(profile,StatementPatternProfile):
        raise TypeError("immutable statement profile required")
    if (not evidence.snapshot_id or evidence.producer != "python-direct-statement-ast-v0.2"
            or profile.schema_version != "0.2"
            or evidence.profile_fingerprint != profile.fingerprint()):
        raise StatementSimilarityError("producer/source profile identity drift")
    analyzed=set(evidence.analyzed_paths)
    unprocessed={p for p,_ in evidence.unprocessed}
    known=analyzed|unprocessed
    hashes=dict(evidence.source_hashes)
    if (not known or len(analyzed)!=len(evidence.analyzed_paths)
            or len(unprocessed)!=len(evidence.unprocessed)
            or analyzed&unprocessed or set(hashes)!=known
            or len(hashes)!=len(evidence.source_hashes)
            or any(not re.fullmatch("[a-f0-9]{64}",h) for h in hashes.values())):
        raise StatementSimilarityError("invalid source scope and digests")
    seen=set()
    grouped:dict[tuple[str,str,str],list[StatementWitness]]=defaultdict(list)
    for w in evidence.witnesses:
        position=(w.path,w.owner_id,w.line)
        if (position in seen or w.path not in analyzed
                or any(w.path.startswith(p) for p in profile.excluded_prefixes)
                or w.source_sha256!=hashes[w.path]
                or not w.owner_id.startswith(f"def::{w.path}::")
                or w.statement_kind not in profile.statement_kinds
                or w.line<1 or w.end_line<w.line
                or w.token_count<profile.min_statement_tokens
                or w.producer!=evidence.producer
                or not re.fullmatch("[a-f0-9]{64}",w.normalized_syntax_sha256)):
            raise StatementSimilarityError("invalid or duplicate source-backed statement witness")
        seen.add(position)
        grouped[(w.owner_id,w.statement_kind,w.normalized_syntax_sha256)].append(w)
    groups=[]
    for (owner,kind,digest),witnesses in sorted(grouped.items()):
        if len(witnesses)<2:
            continue
        groups.append(RepeatedStatementGroup(
            owner,kind,digest,tuple(sorted(witnesses,key=lambda x:(x.path,x.line))),
        ))
    reasons=[]
    if evidence.unprocessed:
        reasons.append("unprocessed_selected_files")
    if evidence.skipped:
        reasons.append("excluded_or_under_minimum_direct_statements")
    if not evidence.witnesses:
        reasons.append("no_eligible_direct_function_statements")
    status=("REPEATED_PATTERNS_OBSERVED" if groups else
            "NO_REPEATS_OBSERVED" if evidence.witnesses else "NOT_EVALUATED")
    return StatementSimilarityReport(
        schema_version="0.2",snapshot_id=evidence.snapshot_id,
        profile_id=profile.profile_id,profile_fingerprint=profile.fingerprint(),
        analyzed_paths=tuple(sorted(analyzed)),unprocessed=evidence.unprocessed,
        coverage_status="partial" if analyzed and unprocessed else
                        "complete" if analyzed else "none",
        eligible_direct_statements=len(evidence.witnesses),
        repeated_statement_occurrences=sum(len(g.witnesses) for g in groups),
        groups=tuple(groups),not_evaluated=tuple(sorted(reasons)),
        status=status,
    )
