"""Non-mutating, exact-source Naming rename migration review packet (#94).

A packet is NOT a migration approval, source patch, verified consumer contract
or guarantee that static lexical references cover runtime/API/DB/ABI bindings.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import io
import re
import tokenize
from typing import Any, Mapping

from codeqa.evaluation.naming_rename_impact_v02 import RenameImpactReport


class MigrationPlanError(ValueError):
    """A purported migration plan has unverifiable source or policy identity."""


BOUNDARIES = (
    "public_api", "external_sdk", "override", "dto_inbound", "dto_outbound",
    "db_physical", "rust_trait", "cpp_virtual_abi", "moose_reserved_dsl",
)
_REV = re.compile(r"git:([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)@([0-9a-f]{40})\Z")
_HASH = re.compile(r"[0-9a-f]{64}\Z")


@dataclass(frozen=True, slots=True)
class MigrationReviewPacket:
    schema_version: str
    baseline_revision: str
    candidate_revision: str
    profile_fingerprint: str
    proposal_verdict: str
    selected_before_paths: tuple[str, ...]
    selected_after_paths: tuple[str, ...]
    compatibility_window: str
    staged_steps: tuple[str, ...]
    rollback_steps: tuple[str, ...]
    boundary_checkpoints: tuple[tuple[str, str], ...]
    unknowns: tuple[str, ...]
    status: str = "HUMAN_REVIEW_REQUIRED"
    mutation_performed: bool = False

    def to_document(self) -> dict[str, Any]:
        raw = asdict(self)
        for field in ("selected_before_paths", "selected_after_paths", "staged_steps", "rollback_steps", "boundary_checkpoints", "unknowns"):
            raw[field] = list(raw[field])
        return raw


def prepare_migration_review_packet(
    *, baseline_revision: str, candidate_revision: str,
    before_sources: Mapping[str, str], after_sources: Mapping[str, str],
    before_sha256: Mapping[str, str], after_sha256: Mapping[str, str],
    profile_fingerprint: str, proposal: RenameImpactReport,
    path_renames: Mapping[str, str],
    source_selection_complete: bool,
    compatibility_window: str, staged_steps: tuple[str, ...],
    rollback_steps: tuple[str, ...],
    boundary_checkpoints: Mapping[str, str],
) -> MigrationReviewPacket:
    left, right = _REV.fullmatch(baseline_revision or ""), _REV.fullmatch(candidate_revision or "")
    if not left or not right or left.group(1) != right.group(1) or left.group(2) == right.group(2):
        raise MigrationPlanError("distinct immutable revisions of the same repository required")
    if not isinstance(profile_fingerprint, str) or not _HASH.fullmatch(profile_fingerprint):
        raise MigrationPlanError("versioned applied profile fingerprint required")
    if (not isinstance(proposal, RenameImpactReport)
            or proposal.revision != baseline_revision
            or proposal.mutation_performed
            or proposal.migration_plan != "HUMAN_REVIEW_REQUIRED"
            or proposal.verdict not in {"UNVERIFIED_PROPOSAL", "BLOCKED_CONTRACT_REVIEW"}):
        raise MigrationPlanError("unapproved or unrelated rename impact report")
    if not all(isinstance(x, Mapping) for x in (
        before_sources, after_sources, before_sha256, after_sha256, path_renames, boundary_checkpoints,
    )):
        raise MigrationPlanError("explicit source/contract mappings required")
    def verify(sources: Mapping[str, str], digests: Mapping[str, str]) -> None:
        if not sources or set(sources) != set(digests):
            raise MigrationPlanError("source coverage and manifest differ")
        for path, content in sources.items():
            if (not isinstance(path, str) or not path or path.startswith("/")
                    or "\\" in path or any(x in ("", ".", "..") for x in path.split("/"))
                    or not isinstance(content, str)
                    or not isinstance(digests[path], str) or not _HASH.fullmatch(digests[path])
                    or sha256(content.encode()).hexdigest() != digests[path]):
                raise MigrationPlanError("forged or unsafe source content digest")
    verify(before_sources, before_sha256)
    verify(after_sources, after_sha256)
    if not set(proposal.selected_paths).issubset(before_sources):
        raise MigrationPlanError("rename proposal references unselected source")
    # A caller-constructed report is not a source-bound producer receipt.
    # Python NAME tokens exclude comments and strings; this remains lexical
    # presence only (not declaration/reference resolution or consumer proof).
    def observed(name: str, sources: Mapping[str, str]) -> bool:
        if not isinstance(name, str) or not name:
            return False
        for path, content in sources.items():
            if path.endswith(".py"):
                if not name.isidentifier():
                    continue
                try:
                    tokens = tuple(tokenize.generate_tokens(
                        io.StringIO(content).readline))
                    if any(token.type == tokenize.NAME and token.string == name
                           for token in tokens):
                        return True
                except (tokenize.TokenError, IndentationError, SyntaxError):
                    # A malformed token stream must not certify name presence.
                    continue
            elif re.search(r"(?<!\\w)" + re.escape(name) + r"(?!\\w)", content):
                # Non-Python sources have no parser-backed binding evidence.
                return True
        return False
    if not observed(proposal.old_name, before_sources):
        raise MigrationPlanError("proposal old identifier absent from exact baseline bytes")
    if type(source_selection_complete) is not bool:
        raise MigrationPlanError("source selection completeness must be a Boolean")

    if (not isinstance(compatibility_window, str) or not compatibility_window.strip()
            or not isinstance(staged_steps, tuple) or not staged_steps
            or not isinstance(rollback_steps, tuple) or not rollback_steps
            or any(not isinstance(s, str) or not s.strip() for s in (*staged_steps, *rollback_steps))):
        raise MigrationPlanError("explicit staged migration, window and rollback plan required")
    if set(boundary_checkpoints) != set(BOUNDARIES) or any(
        status not in {"NOT_EVALUATED", "REVIEW_REQUIRED"}
        for status in boundary_checkpoints.values()
    ):
        raise MigrationPlanError("independent API/DB/ABI approval cannot be self-attested")
    if (any(not isinstance(a, str) or not isinstance(b, str)
            or a not in before_sources or b not in after_sources or a == b
            for a, b in path_renames.items())
            or len(set(path_renames.values())) != len(path_renames)):
        raise MigrationPlanError("invalid or ambiguous explicit source rename mapping")
    mapped = {path_renames.get(path, path) for path in before_sources}
    unknowns = set(proposal.unknowns)
    # The v0.2 draft RenameImpactReport carries revision/path/name metadata
    # but no complete source-manifest digest or applied policy fingerprint.
    # Same revision string alone cannot bind that proposal to these bytes.
    unknowns.add("proposal_source_manifest_binding_not_evaluated")
    unknowns.add("proposal_policy_fingerprint_not_attested")
    if set(proposal.selected_paths) != set(before_sources):
        unknowns.add("proposal_source_selection_differs")
    if mapped != set(after_sources):
        unknowns.add("selected_source_path_coverage_drift")
    if not source_selection_complete:
        unknowns.add("incomplete_source_selection")
    if not observed(proposal.proposed_name, after_sources):
        unknowns.add("proposed_identifier_not_lexically_observed_in_candidate")
    if observed(proposal.old_name, after_sources):
        unknowns.add("old_identifier_still_lexically_observed_in_candidate")
    if any(before_sha256[a] == after_sha256[b] for a, b in path_renames.items()):
        unknowns.add("byte_identical_file_move_not_symbol_rename")
    # Python token observations exclude comments/strings but still cannot prove
    # declaration identity, dynamic references or semantic preservation.
    if any(not path.endswith(".py") for path in (*before_sources, *after_sources)):
        unknowns.add("non_python_lexical_presence_only")
    unknowns.add("lexical_presence_not_source_binding_proof")
    if not path_renames and set(before_sources) == set(after_sources) and all(
        before_sha256[path] == after_sha256[path] for path in before_sources
    ):
        unknowns.add("unchanged_source_bytes_do_not_prove_rename")
    unknowns.update(
        "unverified_contract:" + boundary for boundary, status in boundary_checkpoints.items()
        if status == "NOT_EVALUATED"
    )
    unknowns.add("independent_human_migration_approval_missing")
    return MigrationReviewPacket(
        schema_version="0.1-draft",
        baseline_revision=baseline_revision, candidate_revision=candidate_revision,
        profile_fingerprint=profile_fingerprint, proposal_verdict=proposal.verdict,
        selected_before_paths=tuple(sorted(before_sources)),
        selected_after_paths=tuple(sorted(after_sources)),
        compatibility_window=compatibility_window,
        staged_steps=staged_steps, rollback_steps=rollback_steps,
        boundary_checkpoints=tuple(sorted(boundary_checkpoints.items())),
        unknowns=tuple(sorted(unknowns)),
    )
