# Extraction-aware static P3 review v0.1 — Issue #48

**Opt-in companion.** The established Mechanical v0.1 P3 finding and
threshold remain exactly as published, as do the frozen CCG v0.1, QA
Result/Delta v0.1 and v0.2 comparability conditions. This separate report
measures whether removing a **per-function review trigger** also reduces
calls across an explicitly declared parent+helpers cohort and the **same
selected source population**. It never claims stronger architectural
coupling reduction, runtime behavior or general P3 compliance.

## Original motivating counterexample

Three independent `moose-test-repo` source revisions of
`physics_harness/analysis/field_comparison.py` were frozen in a
controlled experiment. The **Blind refactor was committed before any
codeQA execution**, while Guided used actual measured codeQA P3 evidence.

| Quantity | Base | Blind | Guided |
| --- | ---: | ---: | ---: |
| `compare_named_scalars` outgoing AST calls | 19 | 17 | 12 |
| New helper outgoing AST calls | 0 | 2 | 8 |
| Explicit parent + helper calls | 19 | 19 | **20** |
| P3 per-function threshold | >12 | >12 | >12 |
| P3 review on parent | Yes | Yes | No |

Guided decreases the number of P3 review triggers, yet the relevant
parent+helper sum **increases**, 19 → 20. A tool optimizing only the
trigger could recommend a superficial redistribution of calls.

Source repository and exact independently checked Git blob bytes:
[provenance manifest](../../fixtures/moose-p3-refactor/provenance.json).
The [prior A/B report](../experiments/moose-production-field-blind-vs-codeqa-20261023.md)
also documents 253 bounded differential numerical tests, **not proof of all
possible behavior or physics simulation correctness**.

## API and contract

- Evaluator: `codeqa.evaluation.extraction_aware_p3.compare_extraction_aware_p3`.
- Caller-supplied `ExtractionSpec(path,before_parent,after_parent,before_helpers,
  after_helpers)` explicitly identifies lexical owners. It is **not inferred
  by codeQA**, and any ambiguous, missing or overlapping owner fails closed.
  A renamed parent is allowed only with an explicit before/after mapping.
- Input graphs must be **validated CCG v0.1 facts** from two distinct full
  pinned commits of the **same repository**. Exact source text, Graph coverage, locations and existing Mechanical P3
  `call_metrics` are checked against **Adapter-owned** immutable Python AST
  call witnesses (`codeqa.adapters.python_p3_witness`). The pure evaluator
  consumes `codeqa.core.p3_witness` dataclasses and must never import the
  Python Adapter; orchestration supplies the evidence explicitly. The exact selected
  file population must match and every *other selected file* must remain
  unchanged for attribution to the declared target.
- Profile `profiles/extraction-p3-v0.1.json` is registered as
  `extraction_p3_profile`; its P3 threshold and Mechanical profile
  identity must **exactly match** the existing Mechanical v0.1 profile.
  The output has a separate report schema:
  `contracts/qa/extraction-p3-v0.1.schema.json` /
  `extraction_p3_report_schema`.
- Independent per-arm measures: caller-declared parent and helper call
  sites, selected-scope total, scope review trigger count, function count,
  unknown call targets, coverage/analysis states, source SHA-256 and
  per-file immutable Git snapshot identity.
- Call `extract_python_p3_call_evidence(source_mapping)` separately for
  each pinned snapshot; pass its result as the positional
  `before_call_evidence` / `after_call_evidence` arguments to
  `compare_extraction_aware_p3`. SHA-256 digests bind witnesses to exact
  caller-supplied UTF-8 text, while immutable Git identity remains a
  caller/source-CI responsibility.
- AST calls are counted under the actual lexical function, including async
  and nested definitions. A nested or lambda body is **not borrowed** by
  an enclosing function. The source-call counts/locations must agree with
  the existing CCG `calls` edges. No runtime target resolution is invented.
- An `ExactSyntaxRelocation` is emitted **only** when a before-parent
  `ast.Call` expression's full normalized AST is textually identical to
  a call now present in an explicitly named after-helper. Each witness
  carries owner, source line, unparsed expression and SHA-256 of the
  syntax. This is a **same-syntax candidate**, not proof the call was
  moved or will execute identically. Duplicate expressions are matched
  at most once. Changed arguments or renamed symbols are not matched.
- All findings preserve `LIMITED` / unresolved source facts and never
  convert unknown edges into resolved external dependencies. If any
  selected file fails to parse, the top-level result is
  `INSUFFICIENT_COVERAGE`, never a "clean" improvement.

## Result interpretation

| Result | Bounded meaning |
| --- | --- |
| `REVIEW_TRIGGER_REDISTRIBUTION` | Parent crosses from over-threshold to within threshold, while an explicitly declared helper cohort's call count has **not declined**. A warning about possible metric gaming, not an accusation of improper design. |
| `LOWER_STATIC_CALL_COUNT_OBSERVED` | Both selected-source-scope total and declared cohort total have declined; **only AST call-site counts** were measured. |
| `NO_THRESHOLD_REDISTRIBUTION` | The specific review-trigger redistribution pattern was not observed. Not a P3 PASS. |
| `INSUFFICIENT_COVERAGE` | Selected file parsing incomplete; no winning or losing comparison. |
| `UNCHANGED_SOURCE` | Selected target bytes are identical; no refactor effect can be claimed. |

The explicit parent/child cohort **is not inferred** from arbitrary
before/after code, and does not itself establish legitimate responsibility
boundaries. A lower selected call count may be due to deleting necessary
behavior. The source-only report provides complementary evidence, **not
proof of lower coupling**. Use behavior checks and domain review separately.

## Independent production-code and adversarial checks

`tests/test_extraction_aware_p3.py` validates exact pinned Base/Blind/
Guided source identity and reproduces 19/17/12 parent calls and 19/19/20
cohort calls; synthetic cases verify identical syntax move witnesses,
async/nested function attribution, explicit renames, unchanged source,
unknown imports, partial source coverage, threshold drift, invented call
targets, duplicate/ambiguous owner and fabricated AST edge positions.

`.github/workflows/moose-p3-refactor-conformance.yml` independently
checks out **three exact source Git commits**, byte-compares the three
inert `.py.txt` fixtures against the external repository, then executes
the standalone and full contract test suite. Python source is never
imported or executed by this check. The pinned external A/B differential
execution was previously run under its own separate workflow.

**Non-goals:** No new scoring of P3/P8, no automatic inference that any
helper extraction improves design, no MOOSE solver execution, no changes to
mechanical v0.1 or publication of a universal architecture certification.
