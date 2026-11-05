# QA exchange contracts v0.1

<div align="center">
<p><strong>Versioned findings, measurements and scoped quality evidence.</strong></p>
<p>29 schemas · Source-grounded · No automatic quality certification</p>
</div>

---

## Contract families
All **29 tracked QA schemas** are listed below by responsibility. A schema defines evidence shape, not an automatic quality certification.

### Results & changes
Versioned findings, comparable deltas and source-grounded metrics.

[Result](result-v0.1.schema.json) · [Delta v0.1](delta-v0.1.schema.json) · [Delta v0.2](delta-v0.2.schema.json) · [Metric Snapshot v0.2](metric-snapshot-v0.2.schema.json)
[Source Change v0.2](source-change-v0.2.schema.json)

### Mechanical evidence
Complexity, duplication, similarity and extraction/P3 review signals.

[Complexity](complexity-report-v0.1.schema.json) · [Body Complexity](body-complexity-v0.2.schema.json) · [Duplication](duplication-report-v0.1.schema.json)
[Statement Similarity](statement-similarity-v0.2.schema.json) · [Extraction P3](extraction-p3-v0.1.schema.json) · [Structural P3 Delta](structural-p3-delta-v0.1.schema.json)

### Naming evidence
Optional naming reports, glossary and impact witnesses.

[Naming Report](naming-report-v0.1.schema.json) · [Naming Coverage](python-naming-coverage-v0.2.schema.json) · [Naming Glossary](naming-glossary-v0.1.schema.json)
[Naming Source Delta](naming-source-delta-v0.1.schema.json) · [Rename Impact (draft)](naming-rename-impact-v0.2-draft.schema.json) · [Pinned Ancestor](pinned-ancestor-v0.1.schema.json)
[Directional Fields](directional-fields-v0.1.schema.json)

### Architecture evidence
Inventory, measurements, scenarios, assessments and migration options.

[Inventory](architecture-inventory-v0.1.schema.json) · [Metrics](architecture-metrics-v0.1.schema.json) · [Assessment](architecture-assessment-v0.1.schema.json)
[Scenarios](architecture-scenarios-v0.1.schema.json) · [Opportunities](architecture-opportunities-v0.1.schema.json) · [Migration](architecture-migration-v0.1.schema.json)
[Adapter Boundaries](architecture-adapter-boundaries-v0.1.schema.json) · [Self Diagnostic](architecture-self-diagnostic-v0.1.schema.json)

### External evidence & proof
Typed external evidence admission, independent policy gates and formal binding.

[External Evidence Envelope](external-evidence-envelope-v0.1.schema.json) · [Evidence Policy Gate](evidence-gate-v0.1.schema.json)
[Formal Implementation Binding](formal-implementation-binding-v0.1.schema.json)

## Interpretation & authority
- **QA Result:** scoped coverage and findings, not universal PASS.
- **Quality Delta:** descriptive counts only with strict comparison preconditions.
- **External Evidence:** opt-in integrity/admission, not a QA verdict.
- **Evidence Gate:** independent fail-closed scope; Gate PASS never redefines QA/Mechanical PASS.

Semantic validators remain necessary beyond JSON Schema. CCG v0.1 is unchanged.
The rename-impact schema is **draft**, not authorization to rename.

## Normative references
- [QA result and delta semantics](../../docs/contracts/qa-result-0.1.md)
- [External evidence semantics](../../docs/external-evidence-v01.md) ·
  [ADR 0005 — Admissibility](../../docs/adr/0005-external-evidence-admissibility.md)
- [Evidence Gate decision semantics](../../docs/evidence-gate-v01.md) ·
  [ADR 0006 — Authority](../../docs/adr/0006-evidence-gate-authority.md)
