# codeQA contracts

**Schemas** define what data **may look like**. Policies live in [`profiles/`](../profiles/)
or the consuming repository. Schema validity is not a quality PASS.

## Schemas vs. profiles

- **Schema:** required fields, types, allowed values, and structure.
- **Profile:** repository-selected thresholds, rules, and settings.
- **Examples:** [graph](ccg/graph-v0.1.schema.json) (data) vs.
  [directory roles](../profiles/semantic-directory-roles-v0.1.json) (policy);
  [QA result](qa/result-v0.1.schema.json) (data) vs.
  [complexity](../profiles/complexity-v0.1.json) (thresholds).

## Contract areas

- **[`ccg/`](ccg/README.md)**
  - [graph](ccg/graph-v0.1.schema.json) — source facts, relationships, provenance, and coverage.
- **[`adapters/`](adapters/)**
  - [capability](adapters/capability-v0.1.schema.json) — parser, input/output, supported features, limits.
  - [source-selection](adapters/source-selection-v0.1.schema.json) — pinned snapshot and selected files.
- **[`qa/`](qa/)**
  - [result](qa/result-v0.1.schema.json) / [delta](qa/delta-v0.1.schema.json) — scoped findings and changes.
  - [metrics](qa/metric-snapshot-v0.2.schema.json) / [complexity](qa/complexity-report-v0.1.schema.json) — measurements and reviews.
  - [naming](qa/naming-report-v0.1.schema.json) / [duplication](qa/duplication-report-v0.1.schema.json) — source evidence.
  - [inventory](qa/architecture-inventory-v0.1.schema.json) / [assessment](qa/architecture-assessment-v0.1.schema.json) /
    [scenarios](qa/architecture-scenarios-v0.1.schema.json) — architecture evidence and options.
  - [external evidence](qa/external-evidence-envelope-v0.1.schema.json) /
    [gate](qa/evidence-gate-v0.1.schema.json) / [formal binding](qa/formal-implementation-binding-v0.1.schema.json) —
    external attestations and scoped checks.
- **[`semantic/`](semantic/README.md)**
  - [vocabulary](semantic/architecture-v0.1.vocabulary.json) / [architecture](semantic/architecture-v0.1.schema.json) — ontology and reports.
  - [rule policy](semantic/declared-rule-policy-v0.1.schema.json) /
    [rule report](semantic/declared-rule-report-v0.1.schema.json) — declared roles and findings.
  - [responsibility-behavior](semantic/responsibility-behavior-v0.1.schema.json) — non-scoring syntax observations.

## Future contract areas

Create areas **only when their content is designed**. `contracts/profile/` is
planned, not implemented; it would validate profile structure, not set policy.
