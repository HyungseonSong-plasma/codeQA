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

JSON Schema checks shape and conditional edge fields. The Core validator in
`src/codeqa/core/validation.py` now additionally checks unique node IDs,
edge source/target existence, location span ordering, snapshot-relative paths,
coverage overlap, repeated unprocessed paths and coverage status consistency.
Node/edge facts with a source location must refer to an analyzed file.

`canonical_json(graph)` gives deterministic order/encoding for equivalent
facts. It does **not** prove reproducible extraction or stable ID generation:
Adapters must generate consistent IDs and evidence for identical pinned input,
configuration and tool versions.

No quality scores, thresholds, PASS/FAIL verdicts, repository-specific policy,
or language-specific AST objects belong in the CCG. Those are owned by
`evaluation/`, `profiles/`, and `adapters/` respectively.

## Scope boundary

The contract is implemented in `codeqa.core` by immutable data classes
(`Graph`, `Node`, `Edge`, `Coverage`, `SourceLocation`, etc.).
`parse_graph(document, schema)` validates against the supplied versioned
JSON Schema and then checks graph-wide invariants. It raises
`GraphValidationError` with structured `GraphIssue` details on failure.

The Core **does not** load the schema, read Git, interpret language-specific
ASTs, resolve calls or make quality judgments. Adapters and full semantic
resolution remain separate future implementation tasks.
