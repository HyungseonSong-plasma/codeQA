# codeQA Contracts

> **Schemas define data structures. Profiles define analysis policy.**

Contracts are versioned, language-independent interfaces. Repository-specific
settings live in [`profiles/`](../profiles/) or the consuming repository.

## Schema vs. Profile

| | Schema (`contracts/`) | Profile (`profiles/`) |
| :-- | :-- | :-- |
| **Defines** | Fields, types, and valid structure | Rules, thresholds, and settings |
| **Example** | [CCG graph](ccg/graph-v0.1.schema.json) | [Directory roles](../profiles/semantic-directory-roles-v0.1.json) |
| **Example** | [QA result](qa/result-v0.1.schema.json) | [Complexity thresholds](../profiles/complexity-v0.1.json) |

**Note:** A valid schema does not imply complete analysis or a quality PASS.

## Contract Catalog

### [`ccg/`](ccg/README.md) · Source-code facts

| Contract | Purpose |
| :-- | :-- |
| [Graph v0.1](ccg/graph-v0.1.schema.json) | Source facts, graph relations, provenance, resolution, and coverage |

### [`adapters/`](adapters/) · Language integration

| Contract | Purpose |
| :-- | :-- |
| [Capability v0.1](adapters/capability-v0.1.schema.json) | Parser, input/output, supported features, and limitations |
| [Source Selection v0.1](adapters/source-selection-v0.1.schema.json) | Pinned source snapshot and caller-selected file inventory |

### [`qa/`](qa/README.md) · Quality evidence

| Contracts | Purpose |
| :-- | :-- |
| [Result](qa/result-v0.1.schema.json) · [Delta](qa/delta-v0.1.schema.json) | Findings and quality changes |
| [Metrics](qa/metric-snapshot-v0.2.schema.json) · [Complexity](qa/complexity-report-v0.1.schema.json) | Measurements and review signals |
| [Naming](qa/naming-report-v0.1.schema.json) · [Duplication](qa/duplication-report-v0.1.schema.json) | Source-grounded quality evidence |
| [Inventory](qa/architecture-inventory-v0.1.schema.json) · [Assessment](qa/architecture-assessment-v0.1.schema.json) · [Scenarios](qa/architecture-scenarios-v0.1.schema.json) | Architecture evidence and options |
| [External Evidence](qa/external-evidence-envelope-v0.1.schema.json) · [Gate](qa/evidence-gate-v0.1.schema.json) · [Formal Binding](qa/formal-implementation-binding-v0.1.schema.json) | External attestations and scoped checks |

### [`semantic/`](semantic/README.md) · Architecture semantics

| Contracts | Purpose |
| :-- | :-- |
| [Vocabulary](semantic/architecture-v0.1.vocabulary.json) · [Architecture](semantic/architecture-v0.1.schema.json) | Ontology terms and evidence-based reports |
| [Rule Policy](semantic/declared-rule-policy-v0.1.schema.json) · [Rule Report](semantic/declared-rule-report-v0.1.schema.json) | Declared roles and source-backed findings |
| [Responsibility–Behavior](semantic/responsibility-behavior-v0.1.schema.json) | Non-scoring syntax observations |

---

**Future areas:** Add only when their contents are designed.
`contracts/profile/` is **planned, not implemented**; it would validate
profile structure, not prescribe policy values.
