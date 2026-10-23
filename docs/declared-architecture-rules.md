# Declared Architecture Rule Policy v0.1 (#39)

This is an **opt-in** versioned policy facade. The existing
`evaluation.semantic_layout.evaluate_semantic_layout` remains the **sole
authority** for observed forbidden static role dependencies, missing
declared roles and exact transitional exceptions. The new
`evaluation.architecture_rules.evaluate_declared_architecture_rules`
validates a stricter policy and annotates its findings with versioned rule
IDs, source-line witnesses, exception lifecycle and uncertainty.

## Policy and applicability

- Normative schemas:
  `contracts/semantic/declared-rule-policy-v0.1.schema.json` and
  `contracts/semantic/declared-rule-report-v0.1.schema.json`.
- Policy records `policy_id`, `revision`, `schema_version=0.1`,
  `scope`, `effective_from`, `temporality`, a caller attestation
  `scope_inventory_complete`, roles, allowed/forbidden import directions,
  and exact source/target exceptions with unique ID, rationale, expiry.
- Allowed and forbidden directions must partition the **declared roles**;
  a missing destination, overlap or unversioned policy is invalid.
  These direction constraints are normative repository profile data, not
  a universal language-independent proof of P4/P5 correctness.
- `source_as_of` is an explicitly **caller-supplied** source date (not a
  timestamp inferred or cryptographically certified by codeQA). If the
  policy is retrospective or later than the declared source date, return
  `NOT_EVALUATED`, never apply present-day constraints retroactively as
  authoritative historical violations.
- Exact exceptions are only valid on forbidden role edges. Current
  exceptions remain `REVIEW_REQUIRED`, expired ones are **not exempt** and
  their lifecycle is visible as `EXPIRED_EXCEPTION`.

## Evidence and review semantics

The input CCG and `DependencyGraph` must refer to the **same immutable
snapshot and analyzed/unprocessed file selection**. The underlying role
evaluator checks observed source-to-source imports; each matched finding
is enriched with the actual adapter-observed source line, import expression,
and `top_level` or `conditional_or_deferred` status. Conditional syntax
may not execute: the status expresses a **declared static policy**, not
confirmed runtime coupling.

Unsupported/dynamic/ambiguous dependencies are `NOT_EVALUATED`, not
zero. Partial parsing skips role-absence assessment. A missing declared
role is not a policy violation if the caller has **not attested complete
inventory of the intended scope**; it becomes
`ROLE_ABSENCE_UNPROVEN`. Even a caller attestation is not independently
verified full repository coverage. Clean observed edges never generate
global `PASS`, only `NOT_EVALUATED` for the still-unproven P4/P5
dimensions. All results carry the interpretation
`DECLARED_STATIC_POLICY_ONLY_NOT_P4_P5_CERTIFICATION`.

No old `SemanticArchitecture v0.1` schema, directory-role policy format,
CCG v0.1, Mechanical P1/P3, `PythonAnalysis.to_document()` or frozen
repository root changes.

`tests/test_declared_architecture_rules.py` exercises matching `from`
imports, conditional imports, unknown/dynamic targets, missing owners,
overlapping directions, named/expired exceptions, invalid dates,
retrospective application, incomplete source scope and deterministic
results. The tests also compare forbidden-edge decisions directly to the
existing authority rather than duplicating its decision logic.
