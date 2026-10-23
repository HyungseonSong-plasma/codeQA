# Static dependency metrics and cycle witnesses v0.1 (#36)

The pure `codeqa.evaluation.dependency_metrics.evaluate_dependency_metrics`
consumes the existing `DependencyGraph` separately from Mechanical v0.1 and
frozen CCG v0.1. No new `calls` edges or proven P3/P5 outcomes are created.

**Measured facts:** per-selected-file static fan-out is the count of *distinct
analyzed target paths* matched by syntax, and fan-in the count of distinct
analyzed source paths. Multiple import statements between a pair are
preserved separately as `statement_count` with observed line witnesses and
the number `conditional_or_deferred`. An explicitly supplied self edge
counts toward both degree counts and a length-one cycle; the current Python
extractor ordinarily suppresses self dependencies.

Tarjan SCCs report only components containing cycles and each has a
deterministic **actual-edge** closed-walk witness. Acyclic singleton
components are not reported. The versioned opt-in
`dependency_metrics_profile` defines independent out-degree/cycle-size
review thresholds, never a universal low-coupling score.

**Uncertainty:** unmatched imports, dynamic import syntax and ambiguity are
preserved in `unknown_by_reason` and per-file `unknown_statements`.
Those targets cannot be equated to zero out-degree. Conditional matches are
possible paths, not confirmed execution. `unprocessed_paths` are carried
independently; metrics cover only `analyzed_paths`. Cycle detection cannot
prove runtime recursion or violation of Dependency Inversion.

**Usage:** load profile with
`ResourceRegistry(root).load_json("dependency_metrics_profile")`, call
`DependencyMetricsProfile.from_mapping(...)`, then
`evaluate_dependency_metrics(analysis.dependencies, profile)`.
The standalone opt-in companion deliberately does not change
`PythonAnalysis.to_document()`, the CCG graph, Mechanical P1/P3, QA Result
v0.1 or pinned before/after audits.

**Conformance:** `tests/test_dependency_metrics.py` tests duplicate,
conditional, ambiguous and dynamic imports, multi-node and self cycles,
witness correctness, deterministic input order, invalid graph references,
version/profile rejection and coverage contradictions.
