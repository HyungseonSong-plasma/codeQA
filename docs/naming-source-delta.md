# Source-scoped Naming Delta v0.1 — #75

**Opt-in descriptive companion** to Python Naming v0.1. It is not a
new global quality score, an automatic rename detector, a runtime or
API-compatibility check, or a replacement for strict QA Delta v0.2.

## Trust and comparison boundary

The caller supplies `NamingEvidence` for distinct, full 40-hex
Git revisions in the **same repository**, their exact source bytes,
the *same* `NamingProfile`, and a typed `NamingDeltaManifest` containing
the expected baseline/candidate IDs and profile SHA-256 fingerprint.
The evaluator re-runs the existing pure source-position/hash-aware
Naming v0.1 rule on each revision. Snapshot IDs are
**caller attestations**, not proof that the evaluator fetched Git.

A source rename must be **explicitly** mapped using before/after
paths and both actual file SHA-256 values. Every named declaration
rename is a *caller-declared* pair of before/after lexical identities
(`path, owner, name, kind`) that must exist in the measured source.
The evaluator never guesses a symbol rename from token similarity
or silently links extracted helpers to a previous parent function.

Only identical normalized selected file populations with complete
parsing and no unresolved/excluded naming observations are considered
`COMPARABLE_STATIC_DECLARATIONS`. Unknown ancestor/callback/DTO bindings,
partial parsing, unrecorded path changes or unchanged selected sources
yield `NOT_COMPARABLE` with **no fabricated per-symbol deltas**.
Policy drift and forged rename/source hashes are rejected.

Within a comparable selected scope, the report records
`MATCHED`, `RENAMED_DECLARED`, `ADDED`, `REMOVED` separately
from review-status transitions `INTRODUCED_REVIEW`,
`RESOLVED_REVIEW`, `ADDED_WITH_REVIEW`. It also records
old/new symbol and review counts, plus unresolved counts, **not** a
global claim of architectural progress. No inference of API safety,
semantic improvement, cross-language link resolution or physics
equivalence is permitted.

No changes are made to Naming v0.1, Core CCG, Mechanical or QA
Result/Delta v0.1–v0.2 schemas. `naming_source_delta_schema` is a
separate registered resource. Use
`NamingDeltaManifest.from_mapping(...)` and
`compare_naming_snapshots(..., profile=..., manifest=...)`.

## Evidence and remaining acceptance scope

`tests/test_naming_source_delta.py` covers explicit rename/status
resolution, extraction-driven symbol population change, source path
rename with SHA-256 checks, partial parse, unknown vendor ancestry,
policy or revision mismatch, unchanged source bytes with inconsistent
observations, frozen legacy schemas and deterministic serialization.

It also compares actual frozen Base and Guided
`physics_harness/analysis/field_comparison.py` sources from #48,
pinned at the real MOOSE production commit IDs. CI compares the
source bytes against independently checked-out immutable Git commits
before running this test. This **does not** prove all selected MOOSE
code was parsed, runtime linkage, or independently review the naming
renames.

**Remaining issue #75 acceptance:** comprehensive external schema
and glossary policy drift, public API contract change and negative
tests for manually reviewed declared rename mappings across real
different-commit source files; tested lifecycle for incomplete
selection and generated artifacts. The separate #69 coverage extension
must not be quietly treated as part of v0.1 comparisons.
