# codeQA contracts

The `contracts/` directory contains **versioned, language-independent data
exchange contracts**. A contract describes the information codeQA components
can exchange. Its JSON Schema validates structural requirements such as field
names, types, required properties, and allowed values; additional semantic
invariants may be checked by the corresponding Core validator.

A structurally valid document is **not automatically** an approved policy,
a complete analysis, or a quality PASS.

## Existing contract areas

- [`ccg/`](ccg/README.md) — **Canonical Code Graph (CCG)**: source-code
  facts, graph nodes and edges, provenance, resolution, and coverage (v0.1).
- [`adapters/`](adapters/capability-v0.1.schema.json) — language-adapter
  capability exchange format (v0.1).
- [`qa/`](qa/README.md) — QA results, metric evidence, coverage, and
  quality deltas (v0.1).
- [`semantic/`](semantic/README.md) — Semantic Architecture Ontology
  vocabulary and report schemas (v0.1), separate from the frozen CCG v0.1.

## Contract schema vs. policy profile

| | Contract schema (`contracts/`) | Policy profile (`profiles/` or consuming repository) |
| --- | --- | --- |
| **Purpose** | Defines **which data structures are valid** for exchange. | Defines **which rules, settings, or thresholds to apply** in a particular analysis. |
| **Examples of content** | Required fields, types, versions, permitted enum values, and structural constraints. | Complexity review thresholds, module responsibilities, forbidden import directions, or opt-in settings. |
| **Scope** | Shared, versioned interface across supported producers and consumers. | Repository- or use-case-specific configuration; selection and validation remain explicit. |
| **What validation proves** | The data conforms to the contract's shape (plus separately enforced invariants). | The selected settings satisfy their own policy checks; **not** that all repository code is correct. |

**Concrete codeQA examples:**

1. [`contracts/ccg/graph-v0.1.schema.json`](ccg/graph-v0.1.schema.json)
   defines a graph with `snapshot`, `nodes`, `edges`, and `coverage`.
   It does **not** decide whether one module may depend on another.
   [`profiles/semantic-directory-roles-v0.1.json`](../profiles/semantic-directory-roles-v0.1.json)
   separately defines directory responsibilities and forbidden import directions
   for architecture evaluation.
2. [`contracts/qa/result-v0.1.schema.json`](qa/result-v0.1.schema.json)
   defines how QA findings and evidence are reported.
   [`profiles/complexity-v0.1.json`](../profiles/complexity-v0.1.json)
   supplies example **review thresholds**:
   `max_cyclomatic_proxy_review: 10` and
   `max_branch_nesting_review: 3`. The evaluator applies such settings;
   the result schema does not choose them.

In short: **schemas define the exchange format; profiles select the analysis
policy**. A profile can itself be validated against a schema without becoming
a universal policy. Structural validation must not be confused with semantic
correctness, coverage completeness, or execution evidence.

## Future contract areas

A possible `contracts/profile/` area for **schemas that validate profile
structure** is **planned, not implemented**. If designed and approved, it
would define which profile fields are legal, **not** prescribe repository-specific
policy values. New contract areas and versions should be created only when
their content and intended consumers have been defined.
