# ADR 0005 — External evidence admission is separate from quality verdicts

**Status:** Adopted for the opt-in External Evidence v0.1 implementation
(#98), 2026-10-24.

## Context

External tool outputs can be incomplete, stale or refer to another source
tree. Empty findings after a timeout must not be treated as clean evidence.
Dafny proofs of standalone specs are not automatically bound to a manually
translated C++/Python implementation. Existing CCG/QA Result contracts cannot
safely express these execution- and binding-specific claims as generic PASS.

## Decision

1. Introduce the independently versioned and registered
   `contracts/qa/external-evidence-envelope-v0.1.schema.json`, with an immutable
   Python DTO and strict semantic validator; do **not** change CCG v0.1,
   Naming v0.1, Mechanical or QA Result/Delta v0.1.
2. Common metadata is for *provenance, exact source scope, artifact integrity,
   tool/config/ruleset identity, native execution interpretation and unknowns*.
   Distinct Finding, Type Diagnostic and Formal Proof payloads retain their
   original meanings; there is no universal score or PASS.
3. Admission has `ADMISSIBLE | INADMISSIBLE | INDETERMINATE`. All independent
   source, tool, rules and raw-artifact expectations must be present before
   admission. A separate #99 scoped Gate owns authorization and must default
   to blocking on incomplete/unknown requirements.
4. A verified standalone specification is **not** proof of a deployment.
   #102 must implement separately attested proof-to-implementation binding.
   Until then, formal evidence requested as an implementation proof remains
   `INDETERMINATE`.
5. Adapter-specific exit semantics belong to pinned adapters (#100), not a
   generic `exit_code == 0` assumption. Failed, incomplete and skipped
   runs cannot produce evidence of a clean scan. A diagnostic already observed
   during a partial run must not be discarded.
6. Every future adapter/Policy Gate must include negative controls for
   crashes, false empty reports, coverage/path mismatches, stale tool/config,
   stale source and broken proof binding.

## Consequences

This adds strict bookkeeping and trust gates but **does not** claim
independent proof that an external tool's reported scan scope is truthful.
Such attestation requires integration-specific conformance or execution
isolation. The design may be expanded in a new schema version with durable
artifact storage or stronger binding certificates; no frozen contract is
silently rewritten.

**Verification:** `tests/test_external_evidence_envelope_v01.py`,
`docs/external-evidence-v01.md`, registered resource identity and standard
Repository Layout / Self Audit CI.
