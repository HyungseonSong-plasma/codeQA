# codeQA self-refactor: evidence and limitations (2026-10-23)

## Purpose and decision

This is a bounded, self-directed refactor of the v0.2 Quality Delta comparator.
External CodeRabbit review is **not a requirement**. The experiment does not
assert that satisfying a codeQA threshold establishes better architecture.

Production source/analyzer baseline:
`codeQA@2e8b3a058a3609c7f10a7a984030e1c1ad76c176`.
See the [pinned baseline Self Audit](https://github.com/HyungseonSong-plasma/codeQA/actions/runs/39967193010).

The baseline reported `compare_metric_snapshots` as **118 lines** (>80 P1
review threshold) and **55 AST call sites** (>12 P3 review threshold).
The production selection had 51 Python files, 253 declared functions,
61 P1/P3 review findings and 2,432 unresolved relationships. Its
`coverage=complete` reflects successful parsing of *selected sources*,
not complete static or runtime understanding; `analysis=LIMITED`.

## Code change and measured after-state

The comparator now calls explicit helpers for SHA-verified rename/source
path checks, source-subject matching, unchanged-source checks, observation
matching, and per-rule comparability. The versioned v0.2 exchange contracts,
and the separate v0.1 APIs and schemas, are unchanged.

At [the exact PR head Self Audit](https://github.com/HyungseonSong-plasma/codeQA/actions/runs/39968025839)
(`5789f92c04fee90ceb1c49a6c66d3c3e85ba4caf`):

| Production-scoped property | Baseline | Candidate |
| --- | ---: | ---: |
| Parsed Python files | 51 | 51 |
| Functions | 253 | 257 |
| CCG edges | 2,942 | 2,949 |
| Unresolved relationships | 2,432 | 2,429 |
| **Mechanical review findings overall** | **61** | **61** |
| `compare_metric_snapshots` AST call sites | 55 | 18 |
| `_compare_one_rule` AST call sites | — | 17 |

The parent function no longer triggers the 80-line span review, but
`_compare_one_rule` now triggers a P3 per-function review. The total
61 findings are **unchanged**. These facts cannot establish that total
coupling, maintainability or defect risk improved. Refactoring deliberately
increases implementation surface (helpers and total lines), a cost that
should be justified by clearer separations of responsibility.

### Bounded functional controls

Exact-head Repository Layout Guard and Self Audit passed. The frozen
historical source baseline self-audit regression also passed. Existing
`tests/test_quality_delta_v02.py` checks matched and moved lexical
subjects, SHA-pinned source rename pairs, partial coverage, unsupported
rules, profile/engine/denominator/unit drift, duplicate observation keys,
identical source content with conflicting metrics and serialization
determinism. These controls support compatibility with known contracts;
they do not prove semantic equivalence for all JSON-valid inputs or
real-world maintainability improvement.

### Engineering judgment

**Retain as a bounded internal refactor**, not as a demonstrated
codeQA-optimized quality victory. The source/manifest validation,
per-rule applicability and observation matching now have explicit
boundaries that can be tested and changed independently. That is a
credible, limited rationale; the unchanged finding count and a new
P3 trigger are counterevidence against using the metrics as an
improvement score.

Follow-up analyzer improvements remain separate: helper-extraction-aware
P3 source scope (already added in #48), P6 typed-function body coverage
(already added in #49), and a different, explicitly versioned structural
Delta contract for changed function populations. The existing strict
v0.2 comparison must not silently reinterpret unmatched denominators
as comparable. Duplication analysis currently detects only eligible
whole-function token matches, not intra-function repeated validation
patterns; it also needs a separately scoped and tested enhancement.

No CodeRabbit evaluation was received or relied upon. The work is merged,
if at all, on reproducible CI and scoped technical evidence, **not**
third-party approval or a fabricated P1–P8 certification.
