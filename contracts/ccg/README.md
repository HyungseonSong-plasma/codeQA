# Canonical Code Graph (CCG) contract

**Version:** 0.1 (initial, deliberately minimal). **Owner:** codeQA Core.

The CCG expresses observed **source-code facts**, not quality verdicts. A Python,
C++, Rust or Fortran adapter can produce the same language-neutral graph format.
The source input is a pinned snapshot supplied by the external orchestrator.

## Contract

- **Logical resource ID:** `ccg_schema`. Resolve with
  `ResourceRegistry(root).load_json("ccg_schema")`; do not hard-code this directory.
- **Current schema:** `graph-v0.1.schema.json` (JSON Schema Draft 2020-12).
- **Instance version:** `schema_version: "0.1"`. Schema upgrades require an
  explicit new version; do not silently reinterpret existing instances.

The graph requires five elements:

1. **Graph / snapshot** — immutable source snapshot identity and an instance
   schema version. It does not fetch source or perform GitHub operations.
2. **Node** — stable ID, canonical kind, name and provenance; an optional
   source location for facts with concrete source coordinates.
3. **Edge** — source node, relation, resolution state and provenance. A
   `resolved` edge **must** name a target node ID. An `unresolved` edge
   **must** retain the observed `target_hint` and **must not** invent a target.
4. **Provenance / location** — every node and edge identifies its producer
   and method; location records a snapshot-relative path and line span when
   available. Line numbers are 1-based; columns are 0-based.
5. **Coverage / diagnostics** — explicitly mark complete, partial or no
   analysis; list analyzed and unprocessed paths with reasons. Parsing errors
   and unsupported cases are not equivalent to successful analysis.

An optional `diagnostics` collection preserves parser failures and other
extraction messages. It must not be used to invent graph facts.

## Semantic invariants beyond JSON Schema

The Schema checks shape and conditional edge fields. The future Core validator
must also check unique node IDs, reference existence for edge source/target,
valid source-span ordering, consistent coverage accounting and reproducible
IDs/order for identical pinned inputs and tool configuration. JSON Schema
cannot enforce those graph-wide invariants by itself.

No quality scores, thresholds, PASS/FAIL verdicts, repository-specific policy,
or language-specific AST objects belong in the CCG. Those are owned by
`evaluation/`, `profiles/`, and `adapters/` respectively.

## Scope boundary

This contract does **not** implement a CCG runtime, any language adapter,
semantic resolution or graph-wide validation. It is the v0.1 exchange format
that those components will implement and test against.
