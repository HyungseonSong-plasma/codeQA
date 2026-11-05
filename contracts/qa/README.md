<div align="center">

<h1>QA Contracts</h1>

<p><strong>Versioned findings, measurements and scoped quality evidence.</strong></p>

<p>29 schemas · Source-grounded · No automatic quality certification</p>

</div>

---

## Contract families

Each link points to a concrete JSON Schema. Versions and draft status are
independent: a report shape does not by itself authorize an analysis result.

| Family | Schemas | Purpose |
| :-- | :-- | :-- |
| **QA results & changes** | [Result](result-v0.1.schema.json) · [Delta v0.1](delta-v0.1.schema.json) · [Delta v0.2](delta-v0.2.schema.json) · [Metric Snapshot v0.2](metric-snapshot-v0.2.schema.json) · [Source Change v0.2](source-change-v0.2.schema.json) | Scoped findings, comparable deltas, metric snapshots and source-change evidence. |
| **Mechanical evidence** | [Complexity](complexity-report-v0.1.schema.json) · [Body Complexity](body-complexity-v0.2.schema.json) · [Duplication](duplication-report-v0.1.schema.json) · [Statement Similarity](statement-similarity-v0.2.schema.json) · [Extraction P3](extraction-p3-v0.1.schema.json) · [Structural P3 Delta](structural-p3-delta-v0.1.schema.json) | Complexity, duplication, similarity and P3 extraction review signals. |
| **Naming evidence** | [Naming Report](naming-report-v0.1.schema.json) · [Naming Coverage](python-naming-coverage-v0.2.schema.json) · [Naming Glossary](naming-glossary-v0.1.schema.json) · [Naming Source Delta](naming-source-delta-v0.1.schema.json) · [Rename Impact (draft)](naming-rename-impact-v0.2-draft.schema.json) · [Pinned Ancestor](pinned-ancestor-v0.1.schema.json) · [Directional Fields](directional-fields-v0.1.schema.json) | Optional spelling, glossary, directional-field and source/rename impact reports. |
| **Architecture evidence** | [Inventory](architecture-inventory-v0.1.schema.json) · [Metrics](architecture-metrics-v0.1.schema.json) · [Assessment](architecture-assessment-v0.1.schema.json) · [Scenarios](architecture-scenarios-v0.1.schema.json) · [Opportunities](architecture-opportunities-v0.1.schema.json) · [Migration](architecture-migration-v0.1.schema.json) · [Adapter Boundaries](architecture-adapter-boundaries-v0.1.schema.json) · [Self Diagnostic](architecture-self-diagnostic-v0.1.schema.json) | Inventories, measurement, scenario assessment and source-backed migration proposals. |
| **External evidence & proof** | [External Evidence Envelope](external-evidence-envelope-v0.1.schema.json) · [Evidence Policy Gate](evidence-gate-v0.1.schema.json) · [Formal Implementation Binding](formal-implementation-binding-v0.1.schema.json) | Typed external evidence admission, independent policy gates and formal binding. |

## Interpretation & authority

| Contract | Boundary |
| :-- | :-- |
| [QA Result v0.1](result-v0.1.schema.json) | Records versioned evidence, source scope, coverage, measured-rule outcomes and unsupported principles; not a universal PASS |
| [Quality Delta v0.1](delta-v0.1.schema.json) | Describes review-count changes only when strict comparison preconditions hold |
| [External Evidence Envelope v0.1](external-evidence-envelope-v0.1.schema.json) | **Opt-in** execution integrity and admission eligibility, **not a QA verdict** |
| [Evidence Policy Gate v0.1](evidence-gate-v0.1.schema.json) | Independent fail-closed decisions; a scoped Gate PASS never changes the meaning of Mechanical or QA Result PASS |

JSON Schema enforces structure; **separate fail-closed semantic validators**
must also run where specified. These schemas do not redefine CCG v0.1.
The naming rename-impact contract is a **draft**, not an automatic rename
authorization.

## Normative references

- [QA result and delta semantics](../../docs/contracts/qa-result-0.1.md)
- [External evidence semantics](../../docs/external-evidence-v01.md) ·
  [ADR 0005 — Admissibility](../../docs/adr/0005-external-evidence-admissibility.md)
- [Evidence Gate decision semantics](../../docs/evidence-gate-v01.md) ·
  [ADR 0006 — Authority](../../docs/adr/0006-evidence-gate-authority.md)
