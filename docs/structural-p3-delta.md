# Source-population-aware structural P3 Delta v0.1 (#54)

This is an **opt-in descriptive companion** to the existing **strict** Quality
Delta v0.2. It does **not** relax old per-rule denominator/fingerprint checks
and never declares general P3/P8 quality improvement.

## Data model

`structural_p3_delta(extraction_evidence, schema=...)` consumes a source-
grounded, typed `ExtractionP3Comparison` from the already tested #48 flow.
The caller must independently acquire full immutable commits, selected source
bytes, the validated CCG and Mechanical v0.1 reports, a Python AST witness,
and explicit parent/helper ownership before calling #48. This converter
refuses contradictory measured arithmetic or cross-repository identities.

When both selected-source parse coverages are complete, source revisions
differ and #48's bounded comparison is valid, it reports four *descriptive
static quantities* without imposing equal function counts:

- Total selected **AST call sites** (same selected file population).
- AST calls in the **caller-declared** parent-plus-helper cohort. Explicit
  mapping does **not** prove a semantic equivalence of responsibilities.
- Selected per-function P3 **review-trigger counts**, with both actual
  function populations retained. Review changes are not scores.
- Unresolved call-site totals in the selected source population, explicitly
  **not** runtime-coupling measurements.

Every quantity carries a baseline value, candidate value, arithmetic
difference, unit, scope and interpretation. Warnings include unresolved
call targets, incomplete semantic analysis and limitations inherited
from #48; exact call-syntax relocation witnesses are only syntactic
candidates, not runtime identity.

Partial source parsing, identical source bytes, invalid threshold/profile,
contradictory counts or conflicting source identity cause rejection or
`NOT_COMPARABLE` with **no fabricated deltas**. The source-only status
`COMPARABLE_STATIC_COUNTS` must never be read as a verdict of better
cohesion, lower runtime coupling, preserved behavior or improved physics.

## MOOSE pinned reproduction

Real `physics_harness/analysis/field_comparison.py` commits:

| Source | Parent calls | Helper calls | Declared cohort |
| --- | ---: | ---: | ---: |
| Base | 19 | 0 | 19 |
| Blind | 17 | 2 | 19 |
| Guided | 12 | 8 | **20** |

Thus both refactors may be compared at the selected file-scope despite
newly extracted functions. The Guided parent drops below the P3
review threshold, but **declared cohort calls increase** and the tool
cannot conclude that coupling improved.

See `tests/test_structural_p3_delta.py` for negative controls:
partial parse, changed or identical source bytes, wrong arithmetic,
source repository, profile, rule observations, and the unchanged
`qa_delta_v02_schema` contract. Pinned MOOSE source bytes are checked
independently by `.github/workflows/moose-p3-refactor-conformance.yml`.

API lives in `src/codeqa/evaluation/structural_p3_delta.py`; separate
JSON schema `contracts/qa/structural-p3-delta-v0.1.schema.json` is
registered as `structural_p3_delta_schema`. There is no extra source
extraction in the Evaluation layer and no change to CCG/Mechanical.
