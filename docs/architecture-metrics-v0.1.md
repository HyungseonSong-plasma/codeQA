# Architecture QA B2 — static module boundary metrics v0.1

**Status:** opt-in, source-only, no architecture recommendation. **Issue:** #168 (parent #166). **Implementation:** `src/codeqa/evaluation/architecture/metrics.py`. **Contract:** `contracts/qa/architecture-metrics-v0.1.schema.json`.

## Input and provenance

`analyze_architecture_metrics(inventory, dependencies, role_policy, profile)` consumes B1's exact-commit `architecture-inventory-v0.1` report, the existing language-neutral `DependencyGraph` populated by an adapter, the *same* versioned role policy, and `DependencyMetricsProfile`. It requires identical snapshot identity and policy SHA256, validates tracked/read coverage, rejects ungrounded edges and canonicalizes input ordering. The adapter's static import correspondence is **caller-provided**, not independently authenticated by B2. Path, source SHA256, import line, expression and conditional/deferred execution are preserved as witnesses.

B2 **reuses**, rather than duplicates, `evaluate_dependency_metrics` for file fan-in/out, directed pairs, SCCs and actual closed-cycle witnesses; `analyze_change_impact` for deterministic reverse-import reachability; and `evaluate_semantic_layout` for declared forbidden role dependencies. It does not import AST adapters into the evaluation layer. The caller composes the B1 inventory and adapter evidence.

## Calculation specification (v0.1)

A *module* is a Python file in the graph's `analyzed_paths`; unresolved, unprocessed, excluded and non-Python files do not enter the measured graph. A *resolved directed pair* is a unique `(source_path,target_path)` with at least one graph-provided import-site witness. Duplicate statements or repeated identical graph records do not multiply pairs. Self-imports are excluded by the existing Python adapter; B2 inherits the existing graph model and does not infer runtime imports.

A *declared role* is B1 `POLICY_DECLARED` path ownership from the supplied role policy. Paths outside that declaration are `UNCLASSIFIED` or `OUT_OF_SCOPE`, not silently assigned a role based on filenames. Only pairs with two declared roles enter the within/across-role shares:

```text
within_share = distinct pairs with source_role == target_role
               / (within_declared_pairs + cross_declared_pairs)

cross_share  = distinct pairs with source_role != target_role
               / (within_declared_pairs + cross_declared_pairs)

within_density(role) = observed distinct internal directed pairs
                       / (n_role * (n_role - 1))

cross_out_density(role) = observed distinct outgoing pairs to other declared roles
                          / (n_role * sum(n_other_declared_role))
```

Every denominator is returned explicitly. A zero denominator produces JSON `null`, **not 0 or 1**. These are structural connectivity proxies, not validated cohesion/SRP or coupling quality scores. The group report also exposes observed incoming/outgoing cross-role pair counts, SCC cycle paths with line-level witnesses, and potential reverse-import dependents with shortest witness chains. A graph with no measured edges is distinguishable from an incomplete graph.

`status` is `VIOLATION` when a declared hard dependency is observed, `NOT_EVALUATED` when there are no analyzed modules, `INCOMPLETE` when known coverage/unknown inputs remain, otherwise `EVIDENCE_ONLY`. None is a semantic PASS. `coverage.unknown_by_reason` retains unresolved imports, missing Python graph coverage, unprocessed source, unread tracked source and unsupported non-Python files. External callers and dynamic-import completeness are always `NOT_EVALUATED`.

## Explicit limitations and adversarial cases

An import-site witness is evidence from the existing adapter graph, not a second AST verification. Static imports cannot prove runtime invocation, dynamic dependency completeness, semantic responsibility, package compatibility or safety of a move. Intentional shared utilities and strong internal clustering may be valid architecture, not automatically a defect. A graph with unknown or excluded edges is not certified clean. No Rust/C++ module resolution is inferred. This B2 layer emits **no preselected Naming/Adapter questions**, no relocation scenario and no auto-refactor.

Tests cover deterministic ordering, real codeQA product Python source, renamed-isomorphic graph, cycles, forbidden dependency direction, intentional shared-role paths, deceptive filename semantics, disconnected modules, zero denominator, dynamic unknown, partial parser coverage, excluded/vendor and unsupported language, SHA/policy mismatch, forged graph edge, and schema tampering.

## CI and next stage

The opt-in B2 artifact generator composes the B1 inventory with the existing Python dependency parser on the exact checked-out commit and validates the versioned schema. A successful exact-head CI run is evidence of **bounded static metrics only**. B3 #169 consumes normalized structural signals and may produce zero question opportunities for a healthy source graph; B7 #173 must not turn these proxies into a weighted universal quality verdict.
