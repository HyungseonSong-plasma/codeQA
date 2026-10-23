"""Pure, opt-in token-block duplication review; no inferred behavioral clones."""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from typing import Any

from codeqa.core.duplication import TokenBlock, TokenEvidence


class DuplicationProfileError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class DuplicationProfile:
    profile_id: str
    schema_version: str
    min_block_tokens: int
    normalize_identifiers: bool
    normalize_literals: bool
    excluded_prefixes: tuple[str, ...]

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "DuplicationProfile":
        if not isinstance(value, Mapping) or set(value) != {
            "profile_id", "schema_version", "min_block_tokens",
            "normalize_identifiers", "normalize_literals", "excluded_prefixes",
        }:
            raise DuplicationProfileError("missing or extra duplication profile property")
        prefixes = value["excluded_prefixes"]
        if (not isinstance(value["profile_id"], str) or not value["profile_id"]
                or value["schema_version"] != "0.1"
                or type(value["min_block_tokens"]) is not int or value["min_block_tokens"] < 2
                or type(value["normalize_identifiers"]) is not bool
                or type(value["normalize_literals"]) is not bool
                or not isinstance(prefixes, (list, tuple))
                or len(set(prefixes)) != len(prefixes)
                or any(not isinstance(p, str) or not p or p.startswith("/")
                       or "\\" in p or ".." in p.split("/")
                       or not p.endswith("/") for p in prefixes)):
            raise DuplicationProfileError("unsafe or invalid duplication profile")
        return cls(
            value["profile_id"], "0.1", value["min_block_tokens"],
            value["normalize_identifiers"], value["normalize_literals"],
            tuple(prefixes),
        )

    def fingerprint(self) -> str:
        return sha256(json.dumps({
            **asdict(self), "excluded_prefixes": list(self.excluded_prefixes),
        }, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class DuplicateGroup:
    fingerprint: str
    token_count_per_block: int
    blocks: tuple[TokenBlock, ...]


@dataclass(frozen=True, slots=True)
class DuplicationReport:
    snapshot_id: str
    profile_id: str
    profile_fingerprint: str
    coverage_status: str
    analyzed_paths: tuple[str, ...]
    unprocessed: tuple[tuple[str, str], ...]
    eligible_blocks: int
    evaluated_tokens: int
    duplicate_excess_tokens: int
    observed_duplicate_fraction: float | None
    groups: tuple[DuplicateGroup, ...]
    not_evaluated: tuple[str, ...]
    status: str
    schema_version: str = "0.1"
    interpretation: str = "NORMALIZED_TOKEN_SIMILARITY_NOT_BEHAVIOR_OR_P6_VERDICT"

    def to_document(self) -> dict[str, Any]:
        def serial(value: Any) -> Any:
            if isinstance(value, (tuple, list)):
                return [serial(item) for item in value]
            if isinstance(value, dict):
                return {key: serial(item) for key, item in value.items()}
            return value
        return serial(asdict(self))


def evaluate_duplication(
    observations: TokenEvidence,
    profile: DuplicationProfile,
) -> DuplicationReport:
    if not isinstance(observations, TokenEvidence) or not isinstance(profile, DuplicationProfile):
        raise TypeError("TokenEvidence and DuplicationProfile required")
    if observations.profile_fingerprint != profile.fingerprint():
        raise DuplicationProfileError("profile fingerprint differs from observed tokens")
    included = set(observations.analyzed_paths)
    unprocessed = {path for path, _ in observations.unprocessed}
    if not observations.snapshot_id or included & unprocessed:
        raise DuplicationProfileError("invalid source identity/coverage")
    if len(included) != len(observations.analyzed_paths) or len(unprocessed) != len(observations.unprocessed):
        raise DuplicationProfileError("duplicate source coverage")
    grouped: dict[str, list[TokenBlock]] = defaultdict(list)
    identities = set()
    total = 0
    for block in observations.blocks:
        if (block.node_id in identities or block.path not in included
                or block.token_count < profile.min_block_tokens
                or block.start_line < 1 or block.end_line < block.start_line
                or len(block.fingerprint) != 64):
            raise DuplicationProfileError("invalid source-backed token witness")
        identities.add(block.node_id)
        grouped[block.fingerprint].append(block)
        total += block.token_count
    matching = []
    extra = 0
    for fingerprint, blocks in sorted(grouped.items()):
        if len(blocks) < 2:
            continue
        counts = {block.token_count for block in blocks}
        if len(counts) != 1:
            raise DuplicationProfileError("fingerprint collides with inconsistent token count")
        ordered = tuple(sorted(blocks, key=lambda b: (b.path, b.start_line, b.node_id)))
        matching.append(DuplicateGroup(fingerprint, ordered[0].token_count, ordered))
        extra += (len(ordered)-1)*ordered[0].token_count
    reasons = set()
    if unprocessed:
        reasons.add("unprocessed_selected_files")
    if observations.skipped:
        reasons.add("excluded_or_unmeasured_function_blocks")
    if not total:
        reasons.add("no_eligible_function_blocks")
    if total:
        status = "OBSERVED_DUPLICATION" if matching else "NO_DUPLICATES_OBSERVED"
    else:
        status = "NOT_EVALUATED"
    fraction = extra / total if total else None
    return DuplicationReport(
        snapshot_id=observations.snapshot_id, profile_id=profile.profile_id,
        profile_fingerprint=profile.fingerprint(),
        coverage_status=("partial" if included and unprocessed else
                         "complete" if included else "none"),
        analyzed_paths=tuple(sorted(included)),
        unprocessed=observations.unprocessed,
        eligible_blocks=len(observations.blocks), evaluated_tokens=total,
        duplicate_excess_tokens=extra, observed_duplicate_fraction=fraction,
        groups=tuple(matching), not_evaluated=tuple(sorted(reasons)), status=status,
    )
