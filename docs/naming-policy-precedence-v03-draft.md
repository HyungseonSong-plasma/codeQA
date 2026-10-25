# Naming v0.3 draft — deterministic domain policy precedence (#91)

**Status: AWAITING_HUMAN_REVIEW.** This is an opt-in, source-scoped naming-domain selector, not the generic #99 Policy Gate, a human-approved glossary, an executable rename plan or proof that any identifier has the correct semantics. It does not alter frozen CCG, Naming v0.1, Mechanical, QA Result or Delta schemas.

## Explicit precedence

`NamingPrecedencePolicy.from_mapping(...)` accepts a strict `0.3-draft` policy envelope with `policy_id`, `catalog_sha256`, `profile_sha256`, `review_status=AWAITING_HUMAN_REVIEW` and an explicit list of rules. Each rule has an ID, one of `CHECK_CANDIDATE`, `EXCLUDE_CANDIDATE`, `REVIEW_REQUIRED`, an exact level-specific selector, and no other fields except human owner/reason/expiry for exceptions.

The ordered levels are **catalog → language → repository → path/symbol kind → exact exception**. There must be exactly one catalog baseline. A scope is considered for a decision only when it has a matching language, repository and path/symbol rule; otherwise the result is `NOT_EVALUATED`, even if the catalog baseline exists. At the path/symbol level, the longest **segment-delimited** path prefix wins; `src/codeqa` does not match `src/codeqa_extra`. Exact exceptions require a normalized source path, symbol name, kind, owner, reason, expiry date, and an enclosing explicit path/symbol rule. Expired exceptions are errors, not implicit fallbacks. Duplicate selectors, ambiguous equal-precedence rules and duplicate rule IDs are rejected.

`resolve(...)` requires the exact `git:owner/repo@sha40` revision, matching repository, selected source bytes, date, and the pinned catalog/profile/policy/**expected source file** SHA-256 identities. It recomputes the selected file's SHA-256, **rejects mismatches instead of silently accepting changed source**, and reports the matched rule trace. **The Git revision is a caller attestation**; this module does not fetch the Git blob or prove the source is complete. The policy fingerprint is SHA-256 of canonical sorted-key JSON for the complete policy envelope. If the catalog, profile, policy or selected file identity changes, previously recorded review evidence must be independently revalidated; equal names are not identity proof.

## Safety boundary and unresolved acceptance

Every result has `human_review_required=True` and `semantic_proven=False`. `CHECK_CANDIDATE` is never a PASS, `EXCLUDE_CANDIDATE` is not a silently accepted exception, and `NOT_EVALUATED` is not permission to rename. A positive result cannot certify dynamic Python bindings, imports/reexports, DTO direction, external SDK callbacks, Unicode confusables, physical unit equivalence, Rust trait requirements, C++ ABI, MOOSE DSL, public consumers or SQL migration safety.

The policy remains an **unapproved draft** until a reviewer attributes the actual catalog/glossary, source inventory, positive/negative controls, ownership and exceptions to independently pinned source/profile identities. The #91 original acceptance additionally requires human-adjudicated false positives/negatives, manual inventory outcomes and approved glossary semantics. Neither this draft nor passing tests closes #91.

`tests/test_naming_policy_precedence_v03.py` exercises five-level selection, narrower path precedence, prefix collisions, exact exception matching, missing scopes, stale policy/profile/catalog/source identities, malformed source paths, conflicting overrides, expired exceptions, and refusal to return automatic PASS. This implementation has no filesystem writes or source edits.
