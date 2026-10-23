# ADR 0001 — Canonical contract authority and versioning

**Status:** Accepted, 2026-10-23. **Owner:** codeQA Foundation [#1](https://github.com/HyungseonSong-plasma/codeQA/issues/1).
**Decision scope:** [canonical architecture](../architecture.md).

## Context

The original foundation plan mentioned `docs/contracts/ccg-0.1.md`.
Actual adopted CCG v0.1 artifacts are already maintained in
`contracts/ccg/`, where implementation and validation use their registered
logical ID. Duplicating the schema/text in two locations would create
competing normative authorities. The new Adapter and QA Result contracts
also have their own versions and compatibility promises.

## Decision

1. The **only normative CCG v0.1 source** is the
   [CCG contract](../../contracts/ccg/README.md) together with
   [graph-v0.1.schema.json](../../contracts/ccg/graph-v0.1.schema.json),
   logical resource `ccg_schema`. The originally proposed
   `docs/contracts/ccg-0.1.md` is formally **relocated**, not left as
   unimplemented missing documentation, and no duplicate is introduced.
2. The [Language Adapter v0.1](../contracts/language-adapter-0.1.md)
   declaration and [QA Result v0.1](../contracts/qa-result-0.1.md) are
   **independent versioned contracts** with separate schema identities and
   policy semantics. Existing internal Python reports are not implicitly a
   frozen public API.
3. Contract schemas and semantic validators are both mandatory; version
   upgrades require an approved ADR, a new schema/version, compatibility
   decisions and positive/adversarial conformance fixtures. Never mutate
   frozen CCG v0.1 shape to satisfy a new language adapter or metric.
4. Physical locations can be referenced by versioned
   [logical resource IDs](../../pyproject.toml); moving a resource does
   not change the frozen root layout. Compatible relocations retain
   exactly one normative authority.

## Consequences and alternatives rejected

- We **reject** publishing the same CCG v0.1 rules under two divergent docs
  paths, silently extending accepted schemas, and calling the internal
  `MechanicalReport` structure a universal public result.
- Cross-language conformance (e.g. future [Rust reference #30](https://github.com/HyungseonSong-plasma/codeQA/issues/30))
  must use the same CCG contract. A manual Rust golden fixture must be
  labeled manual rather than presented as a production Rust parser.
- This ADR documents the artifact relocation but does **not** introduce
  a new CCG version or implement untested adapters.

**Verification:** [architecture integrity tests](../../tests/test_architecture_contract_docs.py)
ensure canonical paths and schema/registry identities remain consistent.
