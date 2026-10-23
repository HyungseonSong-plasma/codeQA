# Controlled production-code A/B experiment: Blind vs. codeQA-Guided

Date: 2026-10-23. Outcome: **one per-function P3 review cleared by Guided, but no evidence of reduced total coupling or overall quality superiority**.

## Isolation and sequencing

The actual production target was `moose-test-repo/physics_harness/analysis/field_comparison.py`. Both branches were created independently from `moose-test-repo/main@69be07aab3e5815a1670f7308deb6caf6b49bc79`.

1. **Blind** `experiment/production-field-blind-20261023` committed `9343dfd8a62f51886b1bf80e73f9887076fcd8d9`, a manual extraction of duplicate tolerance-validation logic, **before codeQA was run**.
2. codeQA then measured the unchanged baseline against the Blind commit in [first codeQA run](https://github.com/HyungseonSong-plasma/codeQA/actions/runs/39957923063). Engine pinned to `ff95b021cafb535bbb1b01b4cca2f677af6c9a7c`. It observed 68 source lines and 19 AST calls in `compare_named_scalars`, exceeding the Mechanical P3 threshold `>12`. Blind reduced this to 17 but did not clear the finding.
3. **Guided** `experiment/production-field-codeqa-20261023` started from the *same original commit*; it did not derive from Blind. In response to the measured P3 finding, a per-field numeric comparison was extracted (`4f50707594440ab174580d02affd05894fce417c`). The first [Guided measurement](https://github.com/HyungseonSong-plasma/codeQA/actions/runs/39958272770) showed 49 lines / 14 calls, still above threshold.
4. Guided was revised to move source-value coercion to the field comparison's responsibility (`d8e8d5e2d5154d907953699644263b1dba681be6`). This produced **47 lines / 12 parent calls** and **8 helper calls**, verified in the [final three-arm run](https://github.com/HyungseonSong-plasma/codeQA/actions/runs/39958533417).

Exact commit ancestry is verified; both branches are separate from MOOSE `main`, and neither branch was merged.

## Source-backed observations

All measurements refer to the same explicitly selected **8 files** under `physics_harness/analysis/*.py`. This is not full-repository coverage.

| Measure | Baseline | Blind | Guided |
| --- | ---: | ---: | ---: |
| Parent `compare_named_scalars` span (lines) | 68 | 66 | **47** |
| Parent AST call sites | **19** | 17 | **12** |
| Extracted helper AST call sites | — | 2 | 8 |
| **Sum of parent and new helper AST calls** | 19 | 19 | **20** |
| Overall Mechanical P1/P3 review findings in selected files | 15 | 15 | **14** |
| Duplicate eligible-token fraction | 0 | 0 | 0 |
| P6 function observations `NOT_EVALUATED` | 40 | 41 | 41 |
| Unresolved static imports outside selected files | 36 | 36 | 36 |

The Guided arm passed the **per-function P3 threshold** only by redistributing operations. Importantly, the **combined parent + helper call sites increased 19 → 20**. A reduced review count does **not** prove reduced total call pressure, coupling, maintainability improvement or scientific correctness. Follow-up [#48](https://github.com/HyungseonSong-plasma/codeQA/issues/48) tracks this incentive.

All 8 selected files parsed successfully, but Mechanical analysis remained `LIMITED` due to unresolved relationships outside the selected inputs. P6 complexity remained unavailable on annotated functions (`signature_expressions_not_evaluated`); zero P6 review findings does not mean zero complexity. Follow-up [#49](https://github.com/HyungseonSong-plasma/codeQA/issues/49) tracks this limitation.

## Quality Delta comparability

QA Delta v0.2 correctly did not invent comparable aggregate measurements after helper extraction:
- Base vs. Blind: `PARTIAL`. Only zero observed duplicate fraction was comparable; other rules changed denominators or had limited evidence.
- Base vs. Guided: `NOT_COMPARABLE`. Function extraction changed metric denominators, and key analyses had incomplete evidence.

A descriptive reduction in one Mechanical finding can coexist with a strict overall `NOT_COMPARABLE` Delta outcome; neither should be silently rewritten into a PASS.

## Differential numerical behavior validation

The dedicated GitHub Actions workflow dynamically loaded only the isolated field-comparison module from the three pinned commits (not the MOOSE physics solver) and compared original outputs and exception types/messages for **253 cases**. The cases include empty/missing/mismatched field maps, signed zero, extreme values, NaN and infinity, invalid tolerances and 120 deterministic five-field random vectors. Returned values and input non-mutation were checked.

**Result:** `PRODUCTION_NUMERIC_EQUIVALENCE_PASS: 253 cases, 3 arms`.

This is bounded evidence of behavior preservation on these inputs, not a proof of all possible Mapping implementations, runtime performance, numerical science accuracy or complete equivalence.

## Provenance and future design

- [Machine-readable measurement evidence](../../.github/experiments/moose-production-field-20261023/metrics.json)
- [Final successful workflow](https://github.com/HyungseonSong-plasma/codeQA/actions/runs/39958533417)
- [Original before-Guided codeQA run](https://github.com/HyungseonSong-plasma/codeQA/actions/runs/39957923063)

Next evaluation should incorporate human architecture review, scope-invariant call observations, and regression tests against metric-gaming. The result is a single controlled pilot, not a statistical estimate of general codeQA benefit. Both repository mains were left unmodified.
