<div align="center">

<h1>QA Contracts</h1>

<p><strong>Versioned findings, measurements and scoped quality evidence.</strong></p>

<p>29 schemas · Source-grounded · No automatic quality certification</p>

</div>

---

## Contract families

The following inventory covers all 29 tracked QA schemas. Each contract
describes a specific evidence shape; no entry certifies code quality by itself.

### Results & changes

Versioned findings, comparable deltas and source-grounded metrics.

[Result](result-v0.1.schema.json) · [Delta v0.1](delta-v0.1.schema.json) ·
[Delta v0.2](delta-v0.2.schema.json) ·
[Metric Snapshot v0.2](metric-snapshot-v0.2.schema.json) ·
[Source Change v0.2](source-change-v0.2.schema.json)

### Mechanical evidence

Complexity, duplication, similarity and extraction/P3 review signals.

[Complexity](complexity-report-v0.1.schema.json) ·
[Body Complexity](body-complexity-v0.2.schema.json) ·
[Duplication](duplication-report-v0.1.schema.json) ·
[Statement Similarity](statement-similarity-v0.2.schema.json) ·
[Extraction P3](extraction-p3-v0.1.schema.json) ·
[Structural P3 Delta](structural-p3-delta-v0.1.schema.json)

### Naming evidence

Optional naming reports, glossary and impact witnesses.

[Naming Report](naming-report-v0.1.schema.json) ·
[Naming Coverage](python-naming-coverage-v0.2.schema.json) ·
[Naming Glossary](naming-glossary-v0.1.schema.json) ·
[Naming Source Delta](naming-source-delta-v0.1.schema.json) ·
[Rename Impact (draft)](naming-rename-impact-v0.2-draft.schema.json) ·
[Pinned Ancestor](pinned-ancestor-v0.1.schema.json) ·
[Directional Fields](directional-fields-v0.1.schema.json)

### Architecture evidence

Inventory, measurements, scenarios, assessments and migration options.

[Inventory](architecture-inventory-v0.1.schema.json) ·
[Metrics](architecture-metrics-v0.1.schema.json) ·
[Assessment](architecture-assessment-v0.1.schema.json) ·
[Scenarios](architecture-scenarios-v0.1.schema.json) ·
[Opportunities](architecture-opportunities-v0.1.schema.json) ·
[Migration](architecture-migration-v0.1.schema.json) ·
[Adapter Boundaries](architecture-adapter-boundaries-v0.1.schema.json) ·
[Self Diagnostic](architecture-self-diagnostic-v0.1.schema.json)

### External evidence & proof

[External Evidence Envelope](external-evidence-envelope-v0.1.schema.json) ·
[Evidence Policy Gate](evidence-gate-v0.1.schema.json) ·
[Formal Implementation Binding](formal-implementation-binding-v0.1.schema.json)

## Interpretation & authority

- **QA Result v0.1** records scope, coverage, measured-rule findings and
  unsupported principles. It is not a universal PASS.
- **Quality Delta v0.1** describes review-count changes only when strict
  comparison preconditions hold.
- **External Evidence Envelope v0.1** is an opt-in contract for execution
  integrity and admission eligibility; it is not itself a QA verdict.
- **Evidence Policy Gate v0.1** is independent and fail-closed. Its scoped
  PASS never changes Mechanical or QA Result PASS.

JSON Schema enforces structure; separate fail-closed semantic validation
remains necessary. These schemas do not redefine CCG v0.1. The rename-impact
schema is a **draft**, not an automatic rename authorization.

## Normative references

- [QA result and delta semantics](../../docs/contracts/qa-result-0.1.md)
- [External evidence semantics](../../docs/external-evidence-v01.md) ·
  [ADR 0005 — Admissibility](../../docs/adr/0005-external-evidence-admissibility.md)
- [Evidence Gate decision semantics](../../docs/evidence-gate-v01.md) ·
  [ADR 0006 — Authority](../../docs/adr/0006-evidence-gate-authority.md)
