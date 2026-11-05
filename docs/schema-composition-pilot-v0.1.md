# Schema composition pilot v0.1 — exact, non-migrating evidence

**Issue:** [#282](https://github.com/HyungseonSong-plasma/codeQA/issues/282).  
**Source base:** `main@5da62ae5d2e5fcf44c3eed4f807c951163da834e`.  
**Status:** Read-only experiment; **not** a deployed generator, new public contract or migration.

## Question

Can the 36 versioned JSON Schema files be substantially reduced by
extracting common pieces and composing them? This pilot tests two actual
schemas first; matching property *names* alone is insufficient evidence
for common validation semantics.

## Exact sources and findings

- [Architecture metrics](../contracts/qa/architecture-metrics-v0.1.schema.json):
  source-scoped static measurement report with local `$defs` references.
- [Architecture inventory](../contracts/qa/architecture-inventory-v0.1.schema.json):
  tracked-path/coverage inventory with different coverage fields.

The two documents have exactly equal independent **`$defs.sha256`**
(64 lowercase hex characters) and **`properties.limitations`**
(nonempty string array) subtrees. Their entire `coverage` contracts are
**not equal** and must not be refactored as a single shared type.

| Exact shared subtree | Compact JSON bytes per copy | Copies | Placeholder bytes per copy |
| :-- | --: | --: | --: |
| `$defs.sha256` | 44 | 2 | 22 |
| `properties.limitations` | 55 | 2 | 27 |
| **Total** | **198 bytes before extraction** | | **197 bytes after one copy of each plus placeholders** |

The 197-byte figure assumes an abstract in-memory recipe and omits manifests,
generator implementation, provenance, packaging and test maintenance. The
**theoretical one-byte reduction** is plainly insufficient to justify a
new deployed framework for these *two fragments alone*. Whitespace and
formatted source bytes are not covered by this compact comparison.

## Reproducible executable pilot

[The regression pilot](../tests/test_schema_composition_pilot_v01.py)
extracts the two equal fragments from both immutable schemas, replaces them
with **in-memory placeholders**, and reconstructs two standalone outputs.
The tests require:

1. Every rebuilt schema is **identical as a parsed JSON document** to the
   versioned original and passes Draft 2020-12 meta-schema validation.
2. The existing `$id`, local `$defs` / `$ref` layout and schema-authority
   boundaries remain unchanged. The compiler introduces no new external
   references, remote resolution, on-disk artifacts, or package dependencies.
3. Positive/negative SHA256 examples have identical acceptance decisions.
   Exact reconstructed JSON equality gives stronger structural assurance
   than a handful of examples, **not a proof about all validators or runtime
   consumers**.
4. A same-named field with changed restrictions is rejected, as are unknown,
   recursive or mixed placeholders. Extraction cannot silently broaden
   coverage, omit provenance, or turn unsupported cases into PASS.
5. Source files remain unchanged and no `$fragment` marker appears in any
   normative published contract.

Run it using the existing test runner:
`python -m unittest tests.test_schema_composition_pilot_v01 -v`.
The mandatory `layout` workflow also discovers it.

## Decision

**Do not ship a runtime schema-composition framework based solely on this
pair.** The initial measured structural reuse is real, but negligible relative
to an additional generator, API, file and CI ownership burden. This negative
decision is useful: it guards against a file explosion caused by an unproven
abstraction.

**Next admissible candidate:** investigate the larger, repeated
`architecture-*.schema.json` witness/coverage structures across several
files. Some currently differ because one schema uses a local `$ref` and
another inlines the same restriction. Compare **fully resolved semantic
shapes with exact local reference scope** and measure validator acceptance
(including adversarial fixtures) *before* declaring them reusable. Record
exact revision, matched paths, total savings, introduced maintenance files,
support for standalone installed-wheel validation, and a consumer migration
plan. Prefer a single future versioned generator only when validated
semantic equivalence and reduced total maintenance cost are both shown.

No existing `$id`, `contracts/` path, `ResourceRegistry` logical ID,
profile, CCG v0.1 behavior, workflow, root directory or Samuel pin is changed.
This pilot is **not** authorization for source renames, schema rewrite,
or automatically closing issue #282.
