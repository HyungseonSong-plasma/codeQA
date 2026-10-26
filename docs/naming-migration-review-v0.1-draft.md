# Naming rename migration review packet v0.1-draft (#94)

This is a **non-mutating, human-review-required** complement to the existing
`naming_source_delta` comparator and `naming_rename_impact_v02` lexical
proposal. It does not infer renames from warning counts or create source
patches. A valid packet requires distinct immutable Git revisions of the same
repository, exact per-file SHA-256 for both selections, the original typed
rename proposal, applied Naming profile fingerprint, explicit file-rename
mapping, compatibility window, staged rollout and rollback steps.

Every public/SDK/override/DTO inbound/DTO outbound/SQL physical/Rust trait/
C++ virtual ABI/MOOSE reserved DSL checkpoint must be declared as
`NOT_EVALUATED` or `REVIEW_REQUIRED`. The packet **rejects self-declared
APPROVED/PASS**; independent human and real consumer evidence must be supplied
outside this analyzer. Missing source coverage, dynamic dispatch and public
contract evidence remain visible unknowns. `status` is always
`HUMAN_REVIEW_REQUIRED`; `mutation_performed` is always false.

No frozen CCG, Mechanical, Naming v0.1 or QA Delta contract is changed.
This is a staged-plan evidence template, **not** a human-approved migration
plan or a compatibility-window authorization. Closing #94 still requires
actual independently reviewed public DTO/DB/ABI baselines, rename binding
witnesses and migration/rollback approvals.

## Unbound draft proposal provenance (explicit limitation)

The current v0.2-draft `RenameImpactReport` contains selected paths, a
revision string and policy ID, but **does not contain** a cryptographic digest
of the complete source manifest or the applied policy fingerprint. The
migration review packet verifies the caller-provided before/after bytes and
hashes, but cannot independently establish that a separately supplied rename
proposal was derived from those same bytes or the same policy. It now emits
`proposal_source_manifest_binding_not_evaluated` and
`proposal_policy_fingerprint_not_attested` unconditionally, and
`proposal_source_selection_differs` if the proposal's selected path set is
smaller than the packet's before-source set. Non-Boolean completeness flags
are rejected. These are **unresolved obligations**, not grounds for a safe
rename or a policy PASS; an independently verified source-bound proposal and
human-approved compatibility plan remain required before #94 closure.

## Recomputed lexical negative controls (2026-10-26)

The packet now checks that the proposal's **old spelling actually occurs**
as a lexical token in the independently supplied, digest-verified baseline
source selection; a forged old name fails even if the proposal revision
string matches. It flags an unchanged-byte file move, a proposed name
not observed in the candidate bytes, and an old name still observed after
the candidate change. These observations can match comments/strings and
do **not** establish AST symbol identity, lexical reference completeness,
alias compatibility, verified policy fingerprint or a safe rename. Every
packet therefore still carries `lexical_presence_not_source_binding_proof`,
`proposal_source_manifest_binding_not_evaluated`, and
`proposal_policy_fingerprint_not_attested`, with
`HUMAN_REVIEW_REQUIRED` and no source mutation.

These controls do not replace #94's full immutable-revision comparator,
external SDK/public DTO/DB/ABI evidence or independently reviewed staged
migration/rollback approval. A passing fixture must never authorize a
production rename.

## Python lexical token guard (incremental #94)

For selected `.py` source bytes, the proposal's old and candidate names
must now occur as Python `tokenize.NAME` tokens, not merely in comments or
string literals. The entire token stream must be consumed before the
observation is accepted; malformed tokenization cannot certify presence.
Non-Python files retain only bounded regex lexical evidence and add
`non_python_lexical_presence_only` to the packet's unknowns. An ordinary
Python NAME token may be a reference rather than a declaration, and dynamic
bindings, imports, aliases, public consumers and ABI/DB contracts remain
unresolved. Every packet still requires human review; no migration is run.

## Non-Python lexical boundary correction (#94)

The proposal-only non-Python fallback now uses actual regex word boundaries
around an escaped candidate identifier. A substring such as `OldName` inside
`PrefixOldNameSuffix` is **not** a separate lexical witness. This is still
not a parser-backed C++/Rust binding or external ABI/DSL compatibility proof;
all migration packets remain human-review-required and non-mutating.

## Immutable revision identity hardening

Revision labels use `git:owner/repo@40-hex-SHA` with distinct commits in
the same repository. Dot-segment `owner`/`repo` components are rejected to
avoid treating path-like aliases as independently verified repository
identities. These labels remain **caller-supplied claims**; this draft does
not independently fetch either Git tree, attest an external consumer, or
approve a migration.
