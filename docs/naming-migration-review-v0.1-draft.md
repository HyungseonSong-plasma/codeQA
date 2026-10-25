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
