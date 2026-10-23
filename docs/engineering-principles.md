# Eight engineering principles: observable signals and limits

**Status:** Evidence applicability specification for #27; not an implementation
claim that every principle is evaluated. The eight principles apply **as
design questions to every repository**, while concrete thresholds, roles,
exceptions and effective applicability come from an explicit, versioned
repository profile. This document is normative for **interpretation**, not
a replacement for implemented [quality rules](mechanical-pipeline.md).

This status vocabulary is intentionally **about product capability**, not
`PASS`, `FAIL` or severity:

- `MECHANICAL_HEURISTIC` — active measured Mechanical v0.1 threshold review
  signal, not a proven defect.
- `COMPANION_POLICY_REVIEW` — optional policy-backed architectural evidence,
  separate from the public P1–P8 quality rule verdict.
- `COMPANION_POTENTIAL_ONLY` — optional static impact/quality-change
  descriptions without a P1–P8 quality verdict.
- `NOT_EVALUATED` — no completed universal principle evaluation. Some
  sub-signals may be visible as non-scoring evidence.

## Applicability matrix

| ID | Principle | Implemented assessment (today) | Not certified |
| --- | --- | --- | --- |
| P1 | Single Responsibility | `MECHANICAL_HEURISTIC`: function span in lines | Number or correctness of responsibilities |
| P2 | High Cohesion | `NOT_EVALUATED`: local calls and definitions only | Whether functionality belongs together |
| P3 | Low Coupling | `MECHANICAL_HEURISTIC`: outgoing AST call sites; companion static links | Runtime/semantic coupling |
| P4 | Separation of Concerns | `COMPANION_POLICY_REVIEW`: explicit declared role/edge checks | Completeness or correctness of chosen architecture |
| P5 | Dependency Inversion | `NOT_EVALUATED`: import direction is only a candidate | Abstraction quality or actual inversion |
| P6 | Simplicity | `NOT_EVALUATED`: syntax context is non-scoring | Essential vs accidental complexity |
| P7 | Testability | `NOT_EVALUATED`: CI and tests are verification inputs only | Test adequacy or mutation/coverage effectiveness |
| P8 | Change Safety | `COMPANION_POTENTIAL_ONLY`: potential reverse imports and strict descriptive delta | Regression safety or complete affected test set |

**Public QA Result v0.1 explicitly evaluates only P1/P3 heuristics and
lists P2 and P4–P8 as unsupported**; optional companions do not secretly
upgrade that scope. See [QA Result v0.1](contracts/qa-result-0.1.md) and
[ADR 0003](adr/0003-evidence-coverage-and-verdicts.md).

### P1 — Single Responsibility

- **Status:** `MECHANICAL_HEURISTIC`.
- **Automated evidence now:** `function_span_review` from CCG function/method
  line interval versus `max_function_lines` in the
  [Mechanical profile](../profiles/mechanical-v0.1.json).
- **Context required:** domain responsibilities, reasons to colocate functions,
  cohesion between behaviors, lifecycle/ownership of collaborators.
- **False-positive / negative control:** a long, coherent numeric kernel
  may have one responsibility; a three-line coordinator may span several.
- **Applicability/profile:** only analyzed Python function/method nodes with
  source locations; threshold is repository profile data and can be disabled
  only by an explicitly versioned future applicability protocol.
- **Next evidence gate:** reviewed responsibility annotations, meaningful
  component boundaries and adversarial good-long/bad-short examples; no
  automatic SRP violation label before grounded intent exists.

### P2 — High Cohesion

- **Status:** `NOT_EVALUATED`.
- **Automated evidence now:** CCG definitions, conservative resolved *local*
  calls and static import correspondence provide structure; there is **no**
  cohesion metric, clustering score or P2 rule.
- **Context required:** intended shared state, domain invariants and
  functional roles; distinguish cohesive collaboration from incidental links.
- **False-positive / negative control:** many calls between unrelated
  utilities can look tightly connected; a cohesive interface may delegate
  work without local calls.
- **Applicability/profile:** requires explicit module/component scope and
  versioned criteria, not arbitrary function counts.
- **Next evidence gate:** calibrated cohesion proxy with source-backed
  graph edges plus counterexample fixtures and an agreed profile.

### P3 — Low Coupling

- **Status:** `MECHANICAL_HEURISTIC`.
- **Automated evidence now:** `outgoing_call_sites_review` counts AST `Call`
  sites versus `max_call_sites`, independent of unique targets; source
  [dependency/impact](dependency-impact.md) and
  [cross-module candidates](cross-module-symbol-evidence.md) are separate,
  non-scoring evidence.
- **Context required:** confirmed dependency identity, role/layer boundaries,
  whether the interactions are necessary, stable APIs and injection patterns.
- **False-positive / negative control:** fluent method chains can create many
  AST calls to one logical library; reflection/dynamic imports hide runtime
  dependencies. Unknown targets are not zero coupling.
- **Applicability/profile:** only functions/methods in analyzed Python input;
  limit configured by a versioned Mechanical profile, **not** an absolute
  domain-independent coupling threshold.
- **Next evidence gate:** source-backed distinct-target and external-dependency
  semantics with alias/shadow and DSL adverse cases before true coupling
  assessment.

### P4 — Separation of Concerns

- **Status:** `COMPANION_POLICY_REVIEW`.
- **Automated evidence now:** optional
  [directory role policy](semantic-directory-roles.md) and
  [semantic architecture ontology](semantic-architecture-ontology.md) check
  declared forbidden static dependency edges and bounded exceptions.
  Source facts and normative policy facts remain different.
- **Context required:** who approves architectural ownership and whether
  chosen boundaries reflect actual concerns/domain responsibilities.
- **False-positive / negative control:** a documented transitional dependency
  may be an approved exception; absence of imports does not prove absence of
  side effects, dynamically injected dependencies or boundary violations.
- **Applicability/profile:** only directories/roles and constraints declared
  by the *consumer repository* in an explicit versioned policy. An unknown
  role is `NOT_EVALUATED`, never clean PASS.
- **Next evidence gate:** verified role-ground-truth fixtures, conditional
  import controls, approved exception lifecycle and independent semantic
  evidence. The companion is **not** an implemented general P4 QA rule.

### P5 — Dependency Inversion

- **Status:** `NOT_EVALUATED`.
- **Automated evidence now:** static import directions and declared
  architecture constraints can be inspected, but the analyzer does not
  identify true interfaces, inversion, dependency-injection bindings or a
  universal P5 metric.
- **Context required:** abstract contract ownership, runtime binding and
  intended high-/low-level policy boundaries.
- **False-positive / negative control:** an import into an interface package
  can still conceal a concrete dependency; injection via configuration can
  be invisible to import syntax.
- **Applicability/profile:** depends on explicit architecture/interface
  declarations and a versioned policy; language-neutral Core cannot guess.
- **Next evidence gate:** verified abstraction-role contract, realistic
  Python/Rust examples, positive and adversarial interface-binding evidence.

### P6 — Simplicity

- **Status:** `NOT_EVALUATED`.
- **Automated evidence now:** [contextual call review](contextual-call-review.md)
  counts syntax shapes and control-flow constructs, but there is **no**
  calibrated cyclomatic/cognitive complexity rule, duplication score or
  P6 quality verdict in Mechanical v0.1.
- **Context required:** algorithmic necessity, readability, domain
  constraints, numeric stability and maintainability tradeoffs.
- **False-positive / negative control:** branching in a transparent parser
  can be essential, while short metaprogramming code can be opaque.
- **Applicability/profile:** language-specific complexity definitions must be
  versioned and calibrated; AST construct counts are not transferable scores.
- **Next evidence gate:** algorithm-backed control-flow metrics, duplicate
  detection with exclusions, language conformance and domain counterexamples.

### P7 — Testability

- **Status:** `NOT_EVALUATED`.
- **Automated evidence now:** [layout CI](../.github/workflows/layout.yml),
  [self-audit](self-audit.md), [pinned Samuel fixture](samuel-adapter-conformance.md)
  and [MOOSE audit](contextual-call-review.md) provide *verification
  artifacts*, not a repository's test-quality evaluator.
- **Context required:** test isolation, mutation sensitivity, meaningful
  assertions, failure modes, coverage and ability to inject dependencies.
- **False-positive / negative control:** green tests can miss unexercised
  branches; high line coverage can consist entirely of vacuous assertions.
- **Applicability/profile:** only when reproducible test reports and supported
  coverage/mutation semantics are supplied externally; a missing report is
  `NOT_EVALUATED`, not zero failure.
- **Next evidence gate:** versioned test-result/coverage ingestion, mutation
  controls and stable test-ownership mapping before P7 rule scoring.

### P8 — Change Safety

- **Status:** `COMPANION_POTENTIAL_ONLY`.
- **Automated evidence now:** [reverse-import impact](dependency-impact.md)
  supplies potential affected paths; [QA Delta v0.1](contracts/qa-result-0.1.md)
  compares strictly compatible **review observation counts only**. The
  reproducible self-audit has a frozen historical baseline.
- **Context required:** actual behavior/API compatibility, deployment
  context, risk tolerance, test relevance and runtime dependency evidence.
- **False-positive / negative control:** fewer P1/P3 review observations need
  not mean fewer bugs; an unchanged static import graph may conceal breaking
  dynamic dispatch or configuration changes.
- **Applicability/profile:** Delta requires same engine/version, complete
  selected-path parsing, same rules/units/profile fingerprint and compatible
  scope. This does not prove full source inclusion or change safety.
- **Next evidence gate:** external behavioral/regression compatibility
  evidence, accurate change-to-test mapping, explicit baselines and
  adversarial runtime effects before any safe-change verdict.

## Uncertainty and no-promotion rules

Every report must preserve [coverage, unresolved relationships and actual
analysis limitations](architecture.md). `PASS` is **scoped** to measured
heuristics and can coexist with `analysis_status=LIMITED`. The existence of
a directory-role observation, high call count, passing tests or reduced
review-count delta is never enough to claim broad architectural correctness.
Profile values are supplied as data rather than hardcoded for a specific
repository. The [versioning ADR](adr/0001-contract-authority-and-versioning.md)
and [policy ADR](adr/0002-repository-policy-as-data.md) govern extensions.
