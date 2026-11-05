# codeQA contracts

**Schemas** define what exchanged data **may look like**; repository policies live
in [`profiles/`](../profiles/) or the consuming repository. Schema validity
does not imply a quality PASS.

## Schemas vs. profiles

- **Schema:** fields, types, allowed values, and structural constraints.
- **Profile:** selected thresholds, architecture rules, and opt-in settings.
- **Examples:** [CCG graph](ccg/graph-v0.1.schema.json) defines graph data;
  [directory roles](../profiles/semantic-directory-roles-v0.1.json) sets import
  rules. [QA result](qa/result-v0.1.schema.json) defines report data;
  [complexity profile](../profiles/complexity-v0.1.json) sets review thresholds.

## Contract areas

- [`ccg/`](ccg/README.md)
  - [`graph-v0.1.schema.json`](ccg/graph-v0.1.schema.json) — source snapshot,
    nodes, edges, provenance, resolution, and coverage.
- [`adapters/`](adapters/)
  - [`capability-v0.1.schema.json`](adapters/capability-v0.1.schema.json) —
    parser, input/output, supported features, and limits.
  - [`source-selection-v0.1.schema.json`](adapters/source-selection-v0.1.schema.json) —
    pinned snapshot and caller-selected file inventory.
- [`qa/`](qa/README.md)
  - [`result`](qa/result-v0.1.schema.json) / [`delta`](qa/delta-v0.1.schema.json) —
    scoped QA findings and changes.
  - [`metric-snapshot`](qa/metric-snapshot-v0.2.schema.json) /
    [`complexity-report`](qa/complexity-report-v0.1.schema.json) — measurements and reviews.
  - [`naming-report`](qa/naming-report-v0.1.schema.json) /
    [`duplication-report`](qa/duplication-report-v0.1.schema.json) — naming and duplication evidence.
  - [`architecture-inventory`](qa/architecture-inventory-v0.1.schema.json) /
    [`architecture-assessment`](qa/architecture-assessment-v0.1.schema.json) /
    [`architecture-scenarios`](qa/architecture-scenarios-v0.1.schema.json) —
    architecture evidence and options.
  - [`external-evidence`](qa/external-evidence-envelope-v0.1.schema.json) /
    [`evidence-gate`](qa/evidence-gate-v0.1.schema.json) /
    [`formal-binding`](qa/formal-implementation-binding-v0.1.schema.json) —
    external evidence, scoped gates, and proof-to-code binding.
- [`semantic/`](semantic/README.md)
  - [`vocabulary`](semantic/architecture-v0.1.vocabulary.json) /
    [`architecture`](semantic/architecture-v0.1.schema.json) — ontology terms and reports.
  - [`declared-rule-policy`](semantic/declared-rule-policy-v0.1.schema.json) /
    [`declared-rule-report`](semantic/declared-rule-report-v0.1.schema.json) —
    directory rules and source-backed findings.
  - [`responsibility-behavior`](semantic/responsibility-behavior-v0.1.schema.json) —
    non-scoring syntax and responsibility observations.

## Future contract areas

- Add areas **only when their content is designed**. `contracts/profile/`
  is planned, not implemented; it would validate profile structure,
  not set policy values.
