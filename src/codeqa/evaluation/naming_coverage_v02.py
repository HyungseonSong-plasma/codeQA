"""Pure source-bound extended Python naming companion; no inferred contracts."""
from __future__ import annotations

import re
import unicodedata
from collections import Counter
from collections.abc import Mapping

from codeqa.core.naming import NamingEvidence, NamingProfile
from codeqa.core.naming_coverage_v02 import (
    EXTENDED_KINDS, NamingCoverageError, NamingCoveragePolicy,
    NamingExtendedEvidence, NamingExtendedFinding, NamingExtendedReport,
)
from codeqa.evaluation.naming import evaluate_naming


def _style_ok(name: str, style: str) -> bool:
    if style=="off":
        return True
    if not name.isascii():
        return False
    text=name
    if text.startswith("__") and not text.endswith("__"):
        text=text[2:]
    elif text.startswith("_") and not text.startswith("__"):
        text=text[1:]
    if style=="snake_case":
        return re.fullmatch(r"[a-z][a-z0-9]*(?:_[a-z0-9]+)*",text) is not None
    if style=="UPPER_SNAKE_CASE":
        return re.fullmatch(r"[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)*",text) is not None
    raise NamingCoverageError("unexpected style")


def evaluate_extended_naming(
    baseline:NamingEvidence,
    extended:NamingExtendedEvidence,
    sources:Mapping[str,str],
    *,
    baseline_profile:NamingProfile,
    policy:NamingCoveragePolicy,
)->NamingExtendedReport:
    """Evaluate only *additional* declaration categories, not total Naming coverage."""
    if not isinstance(extended,NamingExtendedEvidence) or not isinstance(policy,NamingCoveragePolicy):
        raise NamingCoverageError("typed immutable naming evidence/policy required")
    # Reject source and baseline v0.1 drift rather than silently replacing evidence.
    evaluate_naming(baseline,sources,baseline_profile)
    if (extended.producer!="python-ast-naming-coverage-v0.2"
            or not extended.snapshot_id
            or extended.snapshot_id!=baseline.snapshot_id
            or extended.source_sha256!=baseline.source_sha256
            or extended.analyzed_paths!=baseline.analyzed_paths
            or extended.unprocessed!=baseline.unprocessed):
        raise NamingCoverageError("cross-version source/coverage identity drift")
    analyzed=set(extended.analyzed_paths)
    seen=set()
    findings=[]
    counts=Counter()
    excluded=0
    uncert=[]
    contract_keys={(c.path,c.owner,c.kind,c.name):c for c in policy.exact_exceptions}
    used=set()
    for s in extended.declarations:
        key=(s.path,s.owner,s.kind,s.name)
        pos=(s.path,s.line,s.column,s.kind,s.name)
        if (pos in seen or key in used or s.path not in analyzed
                or s.kind not in EXTENDED_KINDS
                or s.relation not in ("DECLARED_FINAL","ASSIGNMENT_IN_INIT","UNRESOLVED_SOURCE")
                or s.line<1 or s.column<0 or not s.name or not s.name.isidentifier()):
            raise NamingCoverageError("duplicate, ungrounded or forged declaration witness")
        seen.add(pos)
        used.add(key)
        line=sources[s.path].splitlines()
        if s.line>len(line):
            raise NamingCoverageError("declared line out of source range")
        data=line[s.line-1].encode("utf-8")
        if s.column>=len(data):
            raise NamingCoverageError("declaration byte column out of range")
        visible=data[s.column:]
        if not visible.startswith(s.name.encode("utf-8")):
            # Python's AST NFKC-normalizes identifier spelling, but the original
            # source must be retained as unknown rather than rewritten.
            token=visible.decode("utf-8",errors="strict").split(maxsplit=1)[0]
            token=token.split(":",1)[0].split("=",1)[0].split(".",1)[0].rstrip("(),")
            if unicodedata.normalize("NFKC",token)!=s.name:
                raise NamingCoverageError("source witness name/offset does not match")
            uncert.append((s.path,s.owner,s.line,"unicode_identifier",
                          "source_identifier_NFKC_differs_from_AST"))
            continue
        if any(s.path.startswith(prefix) for prefix in policy.excluded_prefixes):
            excluded+=1
            continue
        style,rule=policy.effective_style(s.path,s.kind)
        contract=contract_keys.get(key)
        if contract is not None:
            status="EXEMPT_BY_DECLARED_CONTRACT"
            reason="attested_exact_exception_not_external_binding_proof"
            origin=f"{contract.provider}@{contract.revision}:{contract.reason}"
        elif s.relation=="UNRESOLVED_SOURCE":
            status="NOT_EVALUATED"
            reason=s.reason
            origin=None
        elif s.name.startswith("__") and s.name.endswith("__"):
            status="EXEMPT_BY_POLICY"
            reason="python_reserved_dunder_name"
            origin=None
        elif style=="off":
            status="NOT_EVALUATED"
            reason="style_disabled_explicitly"
            origin=None
        elif not s.name.isascii():
            status="NOT_EVALUATED"
            reason="unicode_identifier_policy_not_declared"
            origin=None
        else:
            status="CONFORMANT_WITH_APPLIED_RULE" if _style_ok(s.name,style) else "REVIEW_REQUIRED"
            reason="observed_declaration_spelling_matches" if status.startswith("CONFORMANT") else \
                   "declaration_spelling_differs_from_policy"
            origin=None
        findings.append(NamingExtendedFinding(
            s.path,s.owner,s.name,s.kind,s.line,s.column,status,style,rule,reason,origin))
        counts[s.kind]+=1
    for u in extended.uncertainty:
        if (u.path not in analyzed or u.line<1 or
                u.line>len(sources[u.path].splitlines()) or not u.category or not u.reason):
            raise NamingCoverageError("ungrounded uncertainty witness")
        if not any(u.path.startswith(p) for p in policy.excluded_prefixes):
            uncert.append((u.path,u.owner,u.line,u.category,u.reason))
    for entry in extended.unprocessed:
        uncert.append((entry[0],"",0,"unprocessed_source",entry[1]))
    unused=set(contract_keys)-used
    if unused:
        for path,owner,kind,name in sorted(unused):
            uncert.append((path,owner,0,"unused_exact_exception",
                           f"exception_for_unobserved_{kind}:{name}"))
    unknown_count=sum(f.status=="NOT_EVALUATED" for f in findings)+len(uncert)
    reviewed=sum(f.status=="REVIEW_REQUIRED" for f in findings)
    return NamingExtendedReport(
        "0.2",extended.snapshot_id,policy.profile_id,policy.fingerprint(),
        "partial" if extended.unprocessed else
        "complete" if extended.analyzed_paths else "none",
        len(findings),unknown_count,excluded,
        tuple(sorted(counts.items())),
        tuple(sorted(findings,key=lambda f:(f.path,f.line,f.column,f.kind,f.name))),
        tuple(sorted((
            # Using the immutable Core uncertainty type; no unknown silently discarded.
            __import_uncertainty(*item) for item in uncert
        ),key=lambda u:(u.path,u.line,u.category,u.reason))),
        "REVIEW_REQUIRED" if reviewed else
        "NOT_EVALUATED" if unknown_count or excluded or not findings else
        "NO_VIOLATIONS_OBSERVED",
    )


def __import_uncertainty(path:str,owner:str,line:int,category:str,reason:str):
    from codeqa.core.naming_coverage_v02 import NamingUncertainty
    return NamingUncertainty(path,owner,line,category,reason)
