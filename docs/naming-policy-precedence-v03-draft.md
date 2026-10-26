# Naming v0.3 draft — deterministic domain policy precedence (#91)

**Status: AWAITING_HUMAN_REVIEW.** This is an opt-in, source-scoped naming-domain selector, not the generic #99 Policy Gate, a human-approved glossary, an executable rename plan or proof that any identifier has the correct semantics. It does not alter frozen CCG, Naming v0.1, Mechanical, QA Result or Delta schemas.

## Explicit precedence

`NamingPrecedencePolicy.from_mapping(...)` accepts a strict `0.3-draft` policy envelope with `policy_id`, `catalog_sha256`, `profile_sha256`, `review_status=AWAITING_HUMAN_REVIEW` and an explicit list of rules. Each rule has an ID, one of `CHECK_CANDIDATE`, `EXCLUDE_CANDIDATE`, `REVIEW_REQUIRED`, an exact level-specific selector, and no other fields except human owner/reason/expiry for exceptions.

The ordered levels are **catalog → language → repository → path/symbol kind → exact exception**. There must be exactly one catalog baseline. A scope is considered for a decision only when it has a matching language, repository and path/symbol rule; otherwise the result is `NOT_EVALUATED`, even if the catalog baseline exists. At the path/symbol level, the longest **segment-delimited** path prefix wins; `src/codeqa` does not match `src/codeqa_extra`. Exact exceptions require a normalized source path, symbol name, kind, owner, reason, expiry date, and an enclosing explicit path/symbol rule. Expired exceptions are errors, not implicit fallbacks. Duplicate selectors, ambiguous equal-precedence rules and duplicate rule IDs are rejected.

`resolve(...)` requires the exact `git:owner/repo@sha40` revision, matching repository, selected source bytes, date, and the pinned catalog/profile/policy/**expected source file** SHA-256 identities. It recomputes the selected file's SHA-256, **rejects mismatches instead of silently accepting changed source**, and reports the matched rule trace. **The Git revision is a caller attestation**; this module does not fetch the Git blob or prove the source is complete. The policy fingerprint is SHA-256 of canonical sorted-key JSON for the complete policy envelope. If the catalog, profile, policy or selected file identity changes, previously recorded review evidence must be independently revalidated; equal names are not identity proof.

## Safety boundary and unresolved acceptance

Every result has `human_review_required=True` and `semantic_proven=False`. The additive, machine-readable `observation` field is `LEXICAL_ONLY` whenever the selected bytes contain the token (including comment/string-only hits or a missing matching policy scope), and `NOT_OBSERVED` when the token is absent. It is deliberately **not** `AST_DECLARED`, even if a separate AST collector finds a matching declaration. `status=CHECK_CANDIDATE` with `observation=LEXICAL_ONLY` cannot be rendered as a verified declaration or PASS; consumers must join a separately pinned AST site, review outcome, and source identity before claiming ground truth. `CHECK_CANDIDATE` is never a PASS, `EXCLUDE_CANDIDATE` is not a silently accepted exception, and `NOT_EVALUATED` is not permission to rename. A positive result cannot certify dynamic Python bindings, imports/reexports, DTO direction, external SDK callbacks, Unicode confusables, physical unit equivalence, Rust trait requirements, C++ ABI, MOOSE DSL, public consumers or SQL migration safety.

The policy remains an **unapproved draft** until a reviewer attributes the actual catalog/glossary, source inventory, positive/negative controls, ownership and exceptions to independently pinned source/profile identities. The #91 original acceptance additionally requires human-adjudicated false positives/negatives, manual inventory outcomes and approved glossary semantics. Neither this draft nor passing tests closes #91.

`tests/test_naming_policy_precedence_v03.py` exercises five-level selection, narrower path precedence, prefix collisions, exact exception matching, missing scopes, stale policy/profile/catalog/source identities, malformed source paths, conflicting overrides, expired exceptions, and refusal to return automatic PASS. This implementation has no filesystem writes or source edits.

## Pinned-file lexical presence guard (2026-10-26)

A requested symbol absent from the exact selected source bytes now yields
`NOT_EVALUATED` rather than an apparent `CHECK_CANDIDATE` or exception
selection. Prefix-only matches are rejected; a comment/string-only match
remains possible and is explicitly **not declaration or semantic proof**.
This guard is a conservative source-observation prerequisite, not a Python
AST inventory or human-adjudicated glossary. Positive results continue to
require independent review, and Unicode/confusable, reexport, dynamic and
public consumer semantics remain outside this draft selector.

## Candidate source identity guard

The opt-in v0.3 draft refuses Python keywords as candidate symbol spellings,
even when they appear as lexer tokens, and rejects source/selector paths
containing Windows ADS colons or trailing dot/space components. This avoids
portable source identity ambiguity; it does not establish a verified
semantic glossary, external SDK compatibility, independent Git source
attestation, or human approval. No source rename is performed.


## Owner-approved policy principles; unsigned ground truth (2026-10-26)

The owner approved **four requirements**, recorded at [Issue #91 owner decision](https://github.com/HyungseonSong-plasma/codeQA/issues/91#issuecomment-6413057026): explicit canonical `time_step` / `node_id` with noncanonical `timestep` / `nodeid`; Python-only **opt-in** function/method/parameter/field scope; pinned-source AST declaration-site adjudication; and owner final authority, exception accountability, and **180-day review from actual adoption**. This approves requirements **only**. The versioned, non-executable proposal lives in `fixtures/naming-governance/codeqa-owner-policy-direction-v03-proposal.json` with `PENDING_FINAL_ADJUDICATION`, empty path scopes, no adoption date, and null inventory/negative-control human signatures. It cannot be loaded as an approved policy or used for renaming. Frozen v0.1 outputs are unchanged.

`codeqa.core.naming_declaration_evidence_v03.observe_pinned_python` verifies supplied **bytes** against an expected SHA-256 and produces separate Python AST declaration-site observations and decorator **syntax expressions**. A separate trusted Git reader must verify the commit/blob identity: a supplied SHA-256 alone does not authenticate remote provenance. `classify_candidate` reports only `AST_OBSERVED`, `SYNTAX_ONLY`, or `NOT_EVALUATED`, never a human ACCEPT or semantic PASS. The pinned 26-entry one-file fixture has 23 declaration observations and **three** decorator uses (including `@classmethod`), none a renameable declaration. Scope-aware parameter/local/loop observations do not expand the approved opt-in Naming kinds. The existing seven negative cases retain null human outcomes; neither the Grok AI review nor these tests signs them. This is **not** a complete Python binding graph: dynamic bindings, instance attributes, imports/reexports and external consumers need separate review. `CHECK_CANDIDATE` in the precedence selector remains lexical-only and unchanged; do not promote it to AST attestation or #99 Gate PASS.

`tests/test_naming_policy_precedence_v03.py` checks exact pinned-source observation sites, decorator/field/local/parameter distinctions, comment/string/attribute false positives, stale source, malformed AST and the unsigned owner policy envelope. The 180-day clock has **not** started because no policy adoption date has been approved. No automatic rename, final inventory signature, PR merge, or issue closure is authorized.


## Versioned one-file AST observation proposal — **unsigned**

`fixtures/naming-governance/codeqa-ast-review-v03-proposal.json` is a machine-readable, **unapproved** adjudication *candidate packet*, pinned to the same real source Git blob and SHA-256. It records all **26** original sites (23 AST declaration observations, three `SYNTAX_ONLY` decorator uses), all **17** scope-conditional parameter/local/loop omission candidates, and the **seven** existing negative controls, each with **null human outcome**. The separate original v0.2 fixtures remain untouched. The tests cross-check every proposed site against the exact pinned Python AST; they do **not** prove a complete inventory, externally safe rename, semantic equivalence, or actual human review. Missing local/loop observations are not classified as extractor false negatives without a declared coverage denominator. Owner's four policy principles do not supply a final 26-row inventory signature, signed negative outcomes, or authority to merge/close.
