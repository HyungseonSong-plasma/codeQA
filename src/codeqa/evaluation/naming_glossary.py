"""Pure project-declared lexical terminology consistency, no semantic guessing."""
from __future__ import annotations

from dataclasses import asdict,dataclass
from typing import Any

from codeqa.core.naming import NamingEvidence, NamingProfile
from codeqa.core.naming_glossary import (
    NamingGlossaryError,NamingGlossaryProfile,tokenize_identifier,
)
from codeqa.evaluation.naming import evaluate_naming


@dataclass(frozen=True,slots=True)
class GlossaryFinding:
    path: str
    owner: str
    name: str
    kind: str
    line: int
    column: int
    canonical_term: str
    observed_term: str
    status: str
    reason: str


@dataclass(frozen=True,slots=True)
class NamingGlossaryReport:
    schema_version: str
    snapshot_id: str
    glossary_fingerprint: str
    findings: tuple[GlossaryFinding,...]
    inspected_local_declarations: int
    suppressed_external_or_unknown: int
    status: str
    limitations: tuple[str,...]
    interpretation: str = "EXPLICIT_LEXICAL_TERMS_NOT_INFERRED_SEMANTIC_EQUALITY_OR_RENAME"

    def to_document(self)->dict[str,Any]:
        def conv(v:Any)->Any:
            if isinstance(v,(tuple,list)):
                return [conv(x) for x in v]
            if isinstance(v,dict):
                return {k:conv(x) for k,x in v.items()}
            return v
        return conv(asdict(self))


def evaluate_naming_glossary(
    evidence:NamingEvidence,
    sources:dict[str,str],
    *,
    naming_profile:NamingProfile,
    glossary:NamingGlossaryProfile,
)->NamingGlossaryReport:
    """Re-evaluate original source-bound style evidence, then compare declared vocabulary."""
    if not isinstance(glossary,NamingGlossaryProfile):
        raise NamingGlossaryError("immutable glossary profile required")
    base=evaluate_naming(evidence,sources,naming_profile)
    declarations=[x for x in base.findings
                  if any(x.path.startswith(prefix) for prefix in glossary.include_prefixes)]
    accepted={"CONFORMANT_WITH_APPLIED_RULE","REVIEW_REQUIRED"}
    matched=[]
    suppressed=0
    inspected=0
    candidates={}
    for term in glossary.terms:
        for kind in term.kinds:
            for phrase in (term.canonical,*term.aliases):
                tokens=tokenize_identifier(phrase)
                candidates.setdefault(kind,[]).append((
                    tokens,term.canonical,phrase,phrase==term.canonical
                ))
    for kind in candidates:
        candidates[kind].sort(key=lambda x:(-len(x[0]),x[1],x[2]))
    for finding in declarations:
        if finding.status not in accepted:
            suppressed+=1
            continue
        inspected+=1
        tokens=tokenize_identifier(finding.name)
        if not tokens:
            suppressed+=1
            continue
        index=0
        while index<len(tokens):
            matches=[candidate for candidate in candidates.get(finding.kind,())
                     if tuple(tokens[index:index+len(candidate[0])])==candidate[0]]
            if not matches:
                index+=1
                continue
            # Maximal-munch on lexical term boundaries; never infer synonyms.
            best=matches[0]
            token_seq,canonical,observed,is_canonical=best
            matched.append(GlossaryFinding(
                finding.path,finding.owner,finding.name,finding.kind,
                finding.line,finding.column,canonical,observed,
                "CANONICAL_TERM_OBSERVED" if is_canonical
                else "NON_CANONICAL_TERM_REVIEW",
                "exact_declared_canonical_tokens" if is_canonical else
                "exact_project_declared_alias_not_semantic_proof",
            ))
            index+=len(token_seq)
    reviews=any(x.status=="NON_CANONICAL_TERM_REVIEW" for x in matched)
    uncertain=(base.unprocessed or base.unresolved_declarations or
               base.excluded_declarations)
    limits=["external_interface_and_unsupported_declarations_not_inferred"]
    if uncertain:
        limits.append("naming_source_coverage_or_contracts_incomplete")
    if not matched:
        limits.append("no_explicit_glossary_terms_observed")
    return NamingGlossaryReport(
        "0.1",evidence.snapshot_id,glossary.fingerprint(),
        tuple(sorted(matched,key=lambda x:(x.path,x.owner,x.line,x.name,x.canonical_term))),
        inspected,suppressed,
        "REVIEW_TERMINOLOGY" if reviews else
        "NOT_EVALUATED" if uncertain or not matched else
        "NO_NONCANONICAL_TERMS_OBSERVED",
        tuple(limits),
    )
