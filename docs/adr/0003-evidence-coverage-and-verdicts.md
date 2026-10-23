# ADR 0003 — Evidence, coverage, judgment and verdicts stay distinct

**Status:** Accepted, 2026-10-23. **Owner:** codeQA Foundation.
**Decision scope:** [canonical architecture](../architecture.md) and
[QA Result](../contracts/qa-result-0.1.md).

## Context

Source locations and AST syntax provide reliable narrow observations but
cannot in general prove runtime dispatch, correct design intention or safe
change. Past analyses showed that `status=PASS` can coexist with incomplete
parsing and unresolved dependencies. A single global "quality" flag would
misrepresent that uncertainty.

## Decision

1. The caller supplies snapshot identity/selection. The Python Adapter
   extracts source **facts** into CCG with resolution and coverage states,
   leaving unknown edges unresolved.
2. Mechanical observations have provenance, numeric value/unit, source
   location, threshold and rule identity. `REVIEW_REQUIRED` is a candidate
   for contextual investigation, never a mechanically proven SRP/coupling
   defect. Unknown or unsupported principles are `NOT_EVALUATED`.
3. Semantic companions distinguish policy declarations, source witnesses
   and inferred hypotheses. A claimed role conflict or syntax match does
   not imply runtime execution or globally correct architecture.
4. The [public Result v0.1](../contracts/qa-result-0.1.md) scopes `PASS`
   to measured rules and selected analyzed paths and **independently**
   reports `coverage` and `analysis.status/limitations`. No consumer may
   turn `PASS + LIMITED` into a whole-repository clean bill of health.
5. Comparable [Quality Delta v0.1](../../contracts/qa/delta-v0.1.schema.json)
   requires identical comparable rule/profile/unit/source scope, complete
   selected-input parsing and distinct snapshots. Its review-count difference
   is **descriptive**, not established improvement.
6. Self-audit and CI passing demonstrate repeatable **regression/conformance
   checks**, not complete parser soundness or domain-specific correctness.

## Consequences and non-goals

- No fabricated resolved call edges, hidden semantic scoring, heuristic
  FAIL declaration, or assertion that an unlisted file cannot be affected.
- New runtime or domain judgments require new typed evidence, positive and
  adversarial fixtures, separate schema versioning, and explicit policy.
- [P1–P8 matrix](../engineering-principles.md) lists each principle's
  current status, necessary context and negative controls.

**Verification:** the [documentation gate](../../tests/test_architecture_contract_docs.py),
[QA Result tests](../../tests/test_qa_result_contract.py) and
[pinned Samuel conformance](../../tests/test_samuel_adapter_conformance.py)
cover separate semantics. None alone proves universal correctness.
