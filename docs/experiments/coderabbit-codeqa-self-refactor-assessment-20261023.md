# Independent CodeRabbit assessment: codeQA-guided self-refactor (2026-10-23)

**Purpose: evaluate the appropriateness of codeQA's own diagnostic and the
subsequent refactoring, not merely lint/style/CI correctness.** This is a
review experiment. A green CI or fewer Mechanical findings is not an
acceptance verdict and is not evidence of overall P1–P8 compliance.

## Baseline and actual codeQA diagnosis

Source/engine: `codeQA@2e8b3a058a3609c7f10a7a984030e1c1ad76c176`, at
[its immutable Self Audit](https://github.com/HyungseonSong-plasma/codeQA/actions/runs/39967193010).
The actual codeQA pipeline reported for the *production* selection:
51 Python files, 253 functions, 61 Mechanical P1/P3 review findings,
`coverage=complete` for parsing, but `analysis=LIMITED` with 2,432
unresolved edges. It explicitly observed:

- `src/codeqa/evaluation/quality_delta_v02.py::compare_metric_snapshots`:
  **118 declaration lines** versus P1 80-line *review* threshold.
- Same function: **55 syntactic AST call sites** versus P3 12-call
  *review* threshold.

Neither count proves a Single-Responsibility Principle violation,
runtime coupling, defects, or necessarily a valid reason to create
helper functions. The higher count only triggered a manual structure
review. The actual content had independent concerns: immutable source
file/rename validation, per-rule compatibility, lexical observation
matching, and versioned output construction.

## Intervention and hypotheses

The candidate branch starts **directly** from the baseline SHA. It
refactors only the bounded v0.2 `compare_metric_snapshots` evaluation path:

- `_grounded_source_change`: input/path/rename SHA reconciliation
- `_subjects_by_source` and `_source_bytes_unchanged`: observed stable
  lexical identities and exact input identity
- `_observation_differences`: matched/added/removed evidence
- `_compare_one_rule`: independent rule comparability and metric deltas
- `compare_metric_snapshots`: versioned orchestration and schema boundary

This is a **hypothesis** that single-purpose pure helpers better expose
source provenance checks and fail-closed rule semantics. Extraction
increased total file lines, and it may merely redistribute call sites.
We must assess *cohesion, API stability, tests, and total source
complexity*, not optimize the 80/12 thresholds. The codeQA evaluator's
output must stay bytewise consistent for identical canonical input
documents. No CCG, Mechanical, QA Result or Delta v0.1 schema was changed.

## Explicit questions for CodeRabbit

Please provide an **independent, evidence-backed judgment** on three
separate questions, with file/line and concrete counterexamples:

**A. Is the original codeQA analysis itself appropriate?**
Are the P1 function span / P3 AST call-site facts at the pinned SHA
correct, informative, and appropriately calibrated for this function?
What did they *not* measure (real coupling, semantic cohesion, actual
risk, source coverage)? Would the diagnosis have been a false positive
or an insufficient basis for intervention? Assess producer evidence and
limitations before accepting a suggested refactor.

**B. Is the codeQA-guided refactoring appropriate?**
Compare the actual diff with the stated concerns. Does the extracted
boundary represent coherent responsibilities and reduce change risk?
Did we introduce needless indirection, double-validation, allocations,
new failure modes, worse performance or implicit API/behavior change?
Have the original 55 AST calls merely been redistributed or increased?
Please judge correctness and maintainability separately from the changed
Mechanical review count. Challenge unnecessary changes and, if warranted,
recommend reverting the entire refactor.

**C. If either A or B is inadequate, what specifically must codeQA
improve?** Identify root cause at the correct layer
(Adapter evidence / CCG source boundaries / Mechanical rule thresholds /
P3 extraction-aware companion / Delta comparability / Pipeline reporting),
then propose a concrete rule/evidence/contract correction and adversarial
tests that would detect the same bad recommendation **before** a future
refactor. Suggest metrics that remain comparable under helper extraction;
distinguish rule false positives, metric-gaming, missing context, and
missing regression tests. Do **not** assert a general quality score.

## Requested review deliverable

1. **Diagnosis verdict**: `VALID` / `PARTIALLY_SUPPORTED` /
   `UNSUPPORTED`, with specific source evidence and blind spots.
2. **Refactor verdict**: `JUSTIFIED` / `CONDITIONALLY_JUSTIFIED` /
   `UNJUSTIFIED`, with functionality, cohesion, coupling and
   changed-code-size tradeoffs.
3. **CodeQA defects/gaps**: ordered by severity, exact file/rule/producer,
   evidence needed and a negative test that would fail before correction.
4. **Recommendations**: keep/revise/revert this diff, ranked changes to
   analysis methods, tests and governance; explicitly state what was not
   independently verified.

Please include adversarial scenarios: missing/duplicate subject identity,
explicit renames with wrong hashes, incomplete parsing, changed denominator
or profile, unchanged source bytes with contradictory observations,
unclear execution/mutable inputs, and partial reports. Static AST
counts and green GitHub Actions cannot substitute for independent review.

## Review independence and closure condition

Only a **visible CodeRabbit account response** on the PR counts as
CodeRabbit evaluation. The review must address A, B and C rather than only
ordinary style/correctness feedback; if it does not, we must ask it follow-
up questions and record the missing parts as **not reviewed**.
Do not merge while this evaluation is pending. A maintainer must decide
whether to incorporate recommended changes after checking their source
witnesses. CodeRabbit cannot certify scientific correctness or whole-
repository architecture on this limited evidence.
