# Canonical Code Graph (CCG) contract

<div align="center">
<p><strong>Source-code facts with explicit evidence, not quality verdicts.</strong></p>
<p>Schema v0.1 · Language-neutral · Owned by codeQA Core</p>
</div>

---

## Contract
| Item | Contract |
| :-- | :-- |
| **Schema** | [graph-v0.1.schema.json](graph-v0.1.schema.json) · JSON Schema Draft 2020-12 |
| **Instance version** | `schema_version: "0.1"` |
| **Logical resource ID** | `ccg_schema` |
| **Source identity** | One pinned snapshot supplied by the external orchestrator |
| **Implementation** | `codeqa.core` — immutable `Graph`, `Node`, `Edge`, `Coverage`, `SourceLocation` and validators |

Resolve the schema through
`ResourceRegistry(root).load_json("ccg_schema")`, **not** a hard-coded
directory path. Upgrades require a new explicit schema version; existing
instances must not be silently reinterpreted. Language-specific adapters
(Python, C++, Rust, Fortran, etc.) may target the same exchange format;
this does not establish equivalent analyzer implementations.

## Graph structure
The required instance fields are `schema_version`, `snapshot`, `nodes`,
`edges` and `coverage`; `diagnostics` is optional.

| Element | Required semantics |
| :-- | :-- |
| **Snapshot** | Immutable identity of the analyzed source; no fetching or GitHub mutation |
| **Node** | Stable ID, canonical kind, name and producer/method provenance; source location when known |
| **Edge** | Source node, relation, resolution status and provenance. A `resolved` edge has a target node ID; an `unresolved` edge retains `target_hint` and invents no target |
| **Provenance & location** | Snapshot-relative path and span when available; **1-based lines, 0-based columns** |
| **Coverage** | Complete, partial or none; analyzed/unprocessed paths with reasons. Errors and unsupported input are not successful coverage |
| **Diagnostics (optional)** | Parser failures and extraction messages, never invented graph facts |

## Semantic invariants beyond JSON Schema
JSON Schema validates structural and conditional edge fields. The Core
validator in `src/codeqa/core/validation.py` additionally checks:

- Unique node IDs and existence of edge sources and resolved targets.
- Source span ordering and safe snapshot-relative location paths.
- Coverage overlap, repeated unprocessed paths, coverage-status consistency,
  and source-location references restricted to analyzed files.

`parse_graph(document, schema)` enforces the supplied schema and graph-wide
invariants, raising `GraphValidationError` with structured `GraphIssue`
details on failure.

`canonical_json(graph)` gives deterministic ordering and encoding of
equivalent facts. It does **not** prove reproducible extraction or stable IDs;
adapters must produce consistent identifiers and evidence for identical pinned
inputs, configuration and tool versions.

## Ownership & limitations
| Owns | Does not own |
| :-- | :-- |
| Immutable CCG data and validation (`core/`) | Scores, thresholds or PASS/FAIL quality decisions (`evaluation/`, `profiles/`) |
| Language-neutral graph structure | Language-specific AST objects (`adapters/`) |
| Scoped provenance and coverage | Reading Git, loading the schema itself, resolving runtime calls or performing semantic certification |

The Core receives the schema **as data from the caller**. Full cross-file or
runtime call resolution and language-specific analysis remain separate tasks.
