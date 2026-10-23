"""Bounded source-scoped Naming Delta v0.1; no inferred renames or quality score."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from hashlib import sha256
import re
from typing import Any

from codeqa.core.naming import NamingEvidence, NamingProfile
from codeqa.evaluation.naming import NamingFinding, evaluate_naming


class NamingDeltaError(ValueError):
    pass


@dataclass(frozen=True,slots=True)
class PathRename:
    before: str
    after: str
    before_sha256: str
    after_sha256: str


@dataclass(frozen=True,slots=True)
class SymbolRename:
    before_path: str
    before_owner: str
    before_name: str
    after_path: str
    after_owner: str
    after_name: str
    kind: str


@dataclass(frozen=True,slots=True)
class NamingDeltaManifest:
    schema_version: str
    baseline_snapshot_id: str
    candidate_snapshot_id: str
    profile_fingerprint: str
    path_renames: tuple[PathRename,...]
    symbol_renames: tuple[SymbolRename,...]

    @classmethod
    def from_mapping(cls,value:Mapping[str,Any])->NamingDeltaManifest:
        fields=set(cls.__dataclass_fields__)
        if not isinstance(value,Mapping) or set(value)!=fields:
            raise NamingDeltaError("invalid explicit Naming Delta manifest")
        if value["schema_version"]!="0.1":
            raise NamingDeltaError("unknown delta manifest schema")
        if not all(isinstance(value[x],str) and value[x] for x in
                   ("baseline_snapshot_id","candidate_snapshot_id","profile_fingerprint")):
            raise NamingDeltaError("snapshot and policy identities are required")
        if not re.fullmatch("[a-f0-9]{64}",value["profile_fingerprint"]):
            raise NamingDeltaError("invalid applied naming profile fingerprint")
        parsed_paths=[]
        parsed_symbols=[]
        for raw, cls_ in ((value["path_renames"],PathRename),
                          (value["symbol_renames"],SymbolRename)):
            if not isinstance(raw,list):
                raise NamingDeltaError("rename mapping must be a list")
            for item in raw:
                if not isinstance(item,Mapping) or set(item)!=set(cls_.__dataclass_fields__):
                    raise NamingDeltaError("renames require exact before/after identities")
                if any(not isinstance(v,str) for v in item.values()):
                    raise NamingDeltaError("rename identifiers must be strings")
                if cls_ is PathRename:
                    if (not item["before"] or not item["after"]
                            or item["before"]==item["after"]
                            or not re.fullmatch("[a-f0-9]{64}",item["before_sha256"])
                            or not re.fullmatch("[a-f0-9]{64}",item["after_sha256"])):
                        raise NamingDeltaError("invalid source-backed file rename")
                    parsed_paths.append(PathRename(**item))
                else:
                    if (not item["before_path"] or not item["after_path"]
                            or not item["before_name"] or not item["after_name"]
                            or not item["kind"]
                            or (item["before_path"],item["before_owner"],item["before_name"])
                            ==(item["after_path"],item["after_owner"],item["after_name"])):
                        raise NamingDeltaError("symbol rename must change a source identity")
                    parsed_symbols.append(SymbolRename(**item))
        for vals in (
            [(x.before,x.after) for x in parsed_paths],
            [(x.before_path,x.before_owner,x.before_name,x.kind) for x in parsed_symbols],
            [(x.after_path,x.after_owner,x.after_name,x.kind) for x in parsed_symbols],
        ):
            if len(vals)!=len(set(vals)):
                raise NamingDeltaError("duplicate ambiguous rename identity")
        return cls("0.1",value["baseline_snapshot_id"],value["candidate_snapshot_id"],
                   value["profile_fingerprint"],
                   tuple(sorted(parsed_paths,key=lambda x:(x.before,x.after))),
                   tuple(sorted(parsed_symbols,key=lambda x:(
                       x.before_path,x.before_owner,x.before_name,x.kind))))


@dataclass(frozen=True,slots=True)
class NamingDeltaObservation:
    path: str
    kind: str
    before_owner: str | None
    before_name: str | None
    after_owner: str | None
    after_name: str | None
    relationship: str
    before_status: str | None
    after_status: str | None
    review_status_change: str


@dataclass(frozen=True,slots=True)
class NamingDeltaReport:
    schema_version: str
    baseline_snapshot_id: str
    candidate_snapshot_id: str
    profile_fingerprint: str
    status: str
    reasons: tuple[str,...]
    baseline_symbol_count: int
    candidate_symbol_count: int
    baseline_unresolved: int
    candidate_unresolved: int
    baseline_reviews: int
    candidate_reviews: int
    observations: tuple[NamingDeltaObservation,...]
    interpretation: str = "DESCRIPTIVE_NAMING_CHANGE_NOT_PROVEN_DESIGN_OR_INTERFACE_IMPROVEMENT"

    def to_document(self)->dict[str,Any]:
        def convert(x:Any)->Any:
            if isinstance(x,(tuple,list)):
                return [convert(v) for v in x]
            if isinstance(x,dict):
                return {k:convert(v) for k,v in x.items()}
            return x
        return convert(asdict(self))


def _identity(f:NamingFinding)->tuple[str,str,str,str]:
    return (f.path,f.owner,f.name,f.kind)


def compare_naming_snapshots(
    before:NamingEvidence,after:NamingEvidence,
    before_sources:Mapping[str,str],after_sources:Mapping[str,str],
    *,
    profile:NamingProfile,
    manifest:NamingDeltaManifest,
)->NamingDeltaReport:
    """Require pinned identical source-scope/profile and explicit rename witnesses."""
    if not isinstance(manifest,NamingDeltaManifest) or not isinstance(profile,NamingProfile):
        raise NamingDeltaError("typed manifest/profile required")
    def parse_snapshot(value:str)->tuple[str,str]:
        m=re.fullmatch(r"git:([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)@([a-f0-9]{40})",value)
        if not m:
            raise NamingDeltaError("full source Git revisions required")
        return m.group(1),m.group(2)
    lhs,rhs=parse_snapshot(before.snapshot_id),parse_snapshot(after.snapshot_id)
    if (lhs[0]!=rhs[0] or lhs[1]==rhs[1]
            or before.snapshot_id!=manifest.baseline_snapshot_id
            or after.snapshot_id!=manifest.candidate_snapshot_id
            or manifest.profile_fingerprint!=profile.fingerprint()):
        raise NamingDeltaError("repository, revision or applied policy drift")
    older=evaluate_naming(before,before_sources,profile)
    newer=evaluate_naming(after,after_sources,profile)
    before_hashes=dict(before.source_sha256)
    after_hashes=dict(after.source_sha256)
    left=set(before_hashes)
    right=set(after_hashes)
    translate={}
    selected_old=set()
    for mapping in manifest.path_renames:
        if (mapping.before not in left or mapping.after not in right
                or mapping.before==mapping.after
                or mapping.before in selected_old or mapping.after in translate
                or before_hashes[mapping.before]!=mapping.before_sha256
                or after_hashes[mapping.after]!=mapping.after_sha256):
            raise NamingDeltaError("unverified or ambiguous exact source path rename")
        selected_old.add(mapping.before)
        translate[mapping.after]=mapping.before
    if len({translate.get(p,p) for p in right})!=len(right):
        raise NamingDeltaError("file renames collide with another selected source path")
    reasons=[]
    if left!={translate.get(path,path) for path in right}:
        reasons.append("different_selected_source_paths")
    if older.coverage_status!="complete" or newer.coverage_status!="complete":
        reasons.append("incomplete_selected_source_parsing")
    if older.excluded_declarations or newer.excluded_declarations:
        reasons.append("profile_excluded_source_symbols")
    if older.unresolved_declarations or newer.unresolved_declarations:
        reasons.append("unresolved_external_interface_or_symbol_bindings")
    if all(before_hashes.get(translate.get(p,p))==d for p,d in after_hashes.items()):
        if not manifest.path_renames:
            reasons.append("unchanged_selected_source_bytes")
    old={_identity(f):f for f in older.findings}
    new={(translate.get(f.path,f.path),f.owner,f.name,f.kind):f
         for f in newer.findings}
    if len(old)!=len(older.findings) or len(new)!=len(newer.findings):
        raise NamingDeltaError("ambiguous lexical symbol identifiers")
    # Verify that no observed differences are fabricated for unchanged files.
    for new_path,new_sha in after_hashes.items():
        old_path=translate.get(new_path,new_path)
        if old_path in before_hashes and before_hashes[old_path]==new_sha:
            lhs_evidence={(k,f.status,f.rule_id,f.expected)
                          for k,f in old.items() if k[0]==old_path}
            rhs_evidence={(k,f.status,f.rule_id,f.expected)
                          for k,f in new.items() if k[0]==old_path}
            if lhs_evidence!=rhs_evidence:
                raise NamingDeltaError("unchanged source bytes contradict naming evidence")
    renamed_old={}
    renamed_new=set()
    for item in manifest.symbol_renames:
        old_key=(item.before_path,item.before_owner,item.before_name,item.kind)
        new_key=(translate.get(item.after_path,item.after_path),
                 item.after_owner,item.after_name,item.kind)
        if (old_key not in old or new_key not in new
                or item.after_path not in right or item.before_path not in left
                or old_key in renamed_old or new_key in renamed_new
                or old_key==new_key):
            raise NamingDeltaError("rename claim lacks matching source declarations")
        renamed_old[old_key]=new_key
        renamed_new.add(new_key)
    results=[]
    if not reasons:
        processed=set()
        for key,old_f in sorted(old.items()):
            if key in renamed_old:
                newkey=renamed_old[key]
                label="RENAMED_DECLARED"
            elif key in new and key not in renamed_new:
                newkey=key
                label="MATCHED"
            else:
                newkey=None
                label="REMOVED"
            new_f=new.get(newkey) if newkey else None
            if newkey:
                processed.add(newkey)
            status_change=("INTRODUCED_REVIEW" if new_f and
                           new_f.status=="REVIEW_REQUIRED" and old_f.status!="REVIEW_REQUIRED"
                           else "RESOLVED_REVIEW" if new_f and
                           old_f.status=="REVIEW_REQUIRED" and new_f.status!="REVIEW_REQUIRED"
                           else "NO_MEASURED_REVIEW_STATUS_CHANGE")
            results.append(NamingDeltaObservation(
                key[0],key[3],old_f.owner,old_f.name,
                new_f.owner if new_f else None,new_f.name if new_f else None,
                label,old_f.status,new_f.status if new_f else None,status_change))
        for key,new_f in sorted(new.items()):
            if key in processed:
                continue
            results.append(NamingDeltaObservation(
                key[0],key[3],None,None,new_f.owner,new_f.name,
                "ADDED",None,new_f.status,
                "ADDED_WITH_REVIEW" if new_f.status=="REVIEW_REQUIRED" else
                "NO_MEASURED_REVIEW_STATUS_CHANGE"))
    report=NamingDeltaReport(
        "0.1",before.snapshot_id,after.snapshot_id,profile.fingerprint(),
        "COMPARABLE_STATIC_DECLARATIONS" if not reasons else "NOT_COMPARABLE",
        tuple(sorted(set(reasons))),len(older.findings),len(newer.findings),
        older.unresolved_declarations,newer.unresolved_declarations,
        sum(x.status=="REVIEW_REQUIRED" for x in older.findings),
        sum(x.status=="REVIEW_REQUIRED" for x in newer.findings),
        tuple(sorted(results,key=lambda x:(
            x.path,x.kind,x.before_owner or "",x.before_name or "",
            x.after_owner or "",x.after_name or ""
        ))),
    )
    return report
