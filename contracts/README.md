# codeQA contracts

Contract schemas define what data **may look like**.
Concrete repository policies are stored in [`profiles/`](../profiles/) or in the
consuming repository, not here.

## Difference between schemas and profiles

- **Schemas (`contracts/`)** define the versioned structure of exchanged data:
  required fields, data types, allowed values, and structural constraints.
  Corresponding validators may also enforce separate semantic invariants.
- **Profiles (`profiles/` or a consuming repository)** select the rules and
  configuration for a particular analysis, such as thresholds, directory
  responsibilities, forbidden import directions, or opt-in settings.

**Examples from codeQA:**

1. **Code graph vs. architecture policy:** The
   [CCG graph schema](ccg/graph-v0.1.schema.json) defines fields such as
   `snapshot`, `nodes`, `edges`, and `coverage`.
   The [semantic directory roles profile](../profiles/semantic-directory-roles-v0.1.json)
   independently specifies responsibilities and forbidden import directions.
   The graph schema does not decide which dependencies are permitted.
2. **QA result vs. review thresholds:** The
   [QA result schema](qa/result-v0.1.schema.json) defines how findings,
   evidence, coverage, and verdicts are represented.
   The [complexity profile](../profiles/complexity-v0.1.json) selects
   `max_cyclomatic_proxy_review: 10` and
   `max_branch_nesting_review: 3`. The result schema does not set those
   thresholds.

A schema-valid document is **not** automatically an approved policy,
a complete analysis, or a quality PASS. A profile may itself be checked
against a schema without making its chosen values universally applicable.

## Existing contract areas

- [`ccg/`](ccg/README.md)
  - canonical source-code facts
  - graph structure
  - provenance
  - resolution and coverage (v0.1 initially)
- [`adapters/`](adapters/)
  - [`capability-v0.1.schema.json`](adapters/capability-v0.1.schema.json) —
    declares an adapter's language/parser, supported input/output formats,
    feature support, and known limitations; not proof of analysis success.
  - [`source-selection-v0.1.schema.json`](adapters/source-selection-v0.1.schema.json) —
    records an immutable source snapshot, caller-supplied included/excluded
    file inventory, per-file language/category, and inventory completeness;
    not automatic source discovery.
- [`qa/`](qa/README.md)
  - QA results
  - metric evidence
  - coverage and quality deltas (v0.1)
- [`semantic/`](semantic/README.md)
  - Semantic Architecture Ontology vocabulary
  - architecture report schemas (v0.1)
  - separate from frozen CCG v0.1

## Future contract areas

- Future contract areas are created **only when their content is designed**.
  For example, `contracts/profile/` is **planned, not implemented**:
  a future profile schema could validate profile structure, but would not
  prescribe repository-specific policy values.
