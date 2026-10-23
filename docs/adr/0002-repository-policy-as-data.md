# ADR 0002 — Universal questions, repository policy as data

**Status:** Accepted, 2026-10-23. **Owner:** codeQA Foundation.
**Decision scope:** [engineering principles](../engineering-principles.md).

## Context

P1–P8 are cross-repository design principles, not a single set of hardcoded
thresholds or forbidden directories. codeQA must evaluate Python and future
Rust/C++/Fortran inputs without granting any target repository an implicit
special case. Declared roles can be narrower than broad language-level rules.

## Decision

1. All P1–P8 questions are universally **available as vocabulary**. An
   evaluator emits a result for a principle only when an implemented,
   versioned measurement and the required input evidence are available.
2. Thresholds and exclusions are repository-owned, versioned data:
   the [Mechanical profile](../../profiles/mechanical-v0.1.json),
   [root policy](../../profiles/repository-layout.json) and declared
   [directory roles](../../profiles/semantic-directory-roles-v0.1.json)
   are examples, **not universal defaults for every consumer**.
3. Static source facts remain distinct from declared organizational policy.
   A forbidden dependency is evaluated against an explicit declared
   boundary; a previously accepted retrospective policy cannot silently
   certify historical domain semantics.
4. If a principle, file, declared role, source relationship or analyzer
   capability is unsupported, report `NOT_EVALUATED` / uncertainty, not
   negative evidence or PASS. Rules must not branch on repository name.
5. The frozen codeQA [root layout](../repository-structure.md) remains
   unchanged. Changes to layout authority require a separate architecture
   decision and guarded policy change, not a documentation-only edit.

## Consequences / counterexamples

- The current `max_call_sites` may highlight fluent DSL chains without
  establishing excessive coupling; MOOSE physics semantics cannot be inferred
  from generic Python imports.
- A repository with no declared role for a directory cannot be certified
  compliant merely because no forbidden imported module was found.
- A future consumer may supply different thresholds without changing CCG
  facts, Core code or the P1–P8 vocabulary.

**Verification:** [architecture integrity tests](../../tests/test_architecture_contract_docs.py)
enforce the referenced versioned policy paths and interpretation sections.
