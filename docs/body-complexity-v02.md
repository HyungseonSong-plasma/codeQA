# Python body-only complexity evidence v0.2 — P6 (#49)

**Opt-in evidence capability**, not a change to the published Python AST
Complexity v0.1 evaluator, profile, schema or QA Result/Delta v0.1.
The old extractor still emits `NOT_EVALUATED` when decorators or
signature expressions exist, exactly as before. The v0.2 extractor
`extract_python_body_complexity(parsed)` and evaluator
`evaluate_body_complexity(graph,evidence,profile)` are separate entrypoints.

## Declaration vs. body

Python 3.12 AST already distinguishes the function's
`decorator_list`, `args`, `returns`, and `body`.
A bounded **body-only** decision proxy traverses only `body`.
Declarations with annotations, forward-reference string annotations,
side-effectful decorators and defaults are never executed or traversed
in this body metric. They are retained in
`excluded_declaration_scope` with explicit tags, independent from
unmeasured body constructs.

If the body itself contains a lambda body or unsupported type-alias
semantics, the complete function body observation remains
`NOT_EVALUATED`, with null measured values. Nested and async
functions receive independent observations; `if`, `match`,
`except`, loops, Boolean operators and comprehensions reuse the
bounded v0.1 syntax decision rules, **not** a runtime control-flow graph.

`BodyComplexityEvidence` is a language-neutral Core dataclass.
Its `python-ast-body-complexity-v0.2` producer is checked along with
each source-backed CCG function identity/path/line interval.
`BodyComplexityReport` has a new JSON Schema at
`contracts/qa/body-complexity-v0.2.schema.json` and a registered
`body_complexity_v02_schema` resource. Thresholds reuse the existing
versioned v0.1 profile without modifying its values.
No global P6 design-quality verdict is inferred from a low proxy.

## Real experimental reproduction

`tests/test_body_complexity.py` reuses the independently pinned
MOOSE production-code Base, Blind and Guided source fixtures from #48,
whose byte-for-byte Git identity is verified in
`moose-p3-refactor-conformance.yml` (the CI now runs both suites).
For `compare_named_scalars`, the original strict v0.1 observation is
`NOT_EVALUATED` due to a typed declaration; the new body-only record
becomes numerically measured without evaluating any annotation.
The experiment is only the pinned `physics_harness/analysis/field_comparison.py`
source, not MOOSE runtime execution or full-repository assurance.

Test controls cover decorated/annotated/defaulted functions,
forward references, typed nested async functions, match/try, lambda
bodies, partial parse, mismatched CCG locations/producers, deterministic
output and the complete old v0.1 regression behavior.

## Architectural and scoring limits

The existing `PythonAnalysis.to_document()` API is unchanged.
CodeQA cannot measure scientific correctness, all Python runtime
branches or actual annotation evaluation from syntax. The new body
evidence may be offered as a separately versioned *limited* P6
companion to strict Delta v0.2 only after validating both profile
identity and subset coverage; the old Delta must not silently change
the meaning of its rule IDs.
