# codeQA contracts

<div align="center">
<p><strong>Schemas describe data. Profiles select repository policy.</strong></p>
<p>Versioned · Language-independent · Evidence-scoped</p>
<p>
<a href="#schema-vs-profile">Schema vs. Profile</a> ·
<a href="#contract-catalog">Contract Catalog</a> ·
<a href="#future-areas">Future Areas</a>
</p>
</div>

---

## Schema vs. Profile
| | **Schema** (`contracts/`) | **Profile** (`profiles/`) |
| :-- | :-- | :-- |
| **Defines** | Fields, types, valid structures | Rules, thresholds, scoped settings |
| **Example · graph** | [CCG graph](ccg/graph-v0.1.schema.json) | [Directory roles](../profiles/semantic-directory-roles-v0.1.json) |
| **Example · quality** | [QA result](qa/result-v0.1.schema.json) | [Complexity thresholds](../profiles/complexity-v0.1.json) |

A schema-valid document is **not** automatically a complete analysis,
approved policy, or quality PASS. Schema evolution and consumer policy
adoption are separate decisions.

## Contract Catalog
### 01 · [`ccg/`](ccg/README.md) — Canonical source facts
| Contract | Defines |
| :-- | :-- |
| [Graph v0.1](ccg/graph-v0.1.schema.json) | Source snapshot, nodes, edges, provenance, resolution and coverage |

### 02 · [`adapters/`](adapters/) — Language integration
| Contract | Defines |
| :-- | :-- |
| [Capability v0.1](adapters/capability-v0.1.schema.json) | Parser details, input/output, feature support and limitations |
| [Source Selection v0.1](adapters/source-selection-v0.1.schema.json) | Pinned snapshot and caller-supplied included/excluded file inventory |

### 03 · [`qa/`](qa/README.md) — Quality and architecture evidence
| Contract group | Defines |
| :-- | :-- |
| [Result](qa/result-v0.1.schema.json) · [Delta](qa/delta-v0.1.schema.json) | Scoped findings and descriptive quality changes |
| [Metrics](qa/metric-snapshot-v0.2.schema.json) · [Complexity](qa/complexity-report-v0.1.schema.json) | Source-grounded measurements and review signals |
| [Naming](qa/naming-report-v0.1.schema.json) · [Duplication](qa/duplication-report-v0.1.schema.json) | Optional naming and duplication evidence |
| [Architecture inventory](qa/architecture-inventory-v0.1.schema.json) · [Assessment](qa/architecture-assessment-v0.1.schema.json) · [Scenarios](qa/architecture-scenarios-v0.1.schema.json) | Architecture facts, analysis and alternatives |
| [External Evidence](qa/external-evidence-envelope-v0.1.schema.json) · [Gate](qa/evidence-gate-v0.1.schema.json) · [Formal Binding](qa/formal-implementation-binding-v0.1.schema.json) | External evidence admission and scoped checks |

The [QA directory guide](qa/README.md) indexes all current schemas by
responsibility, including draft and opt-in companions.

### 04 · [`semantic/`](semantic/README.md) — Architecture semantics
| Contract group | Defines |
| :-- | :-- |
| [Vocabulary](semantic/architecture-v0.1.vocabulary.json) · [Architecture report](semantic/architecture-v0.1.schema.json) | Ontology terms and evidence-based reports |
| [Declared rule policy](semantic/declared-rule-policy-v0.1.schema.json) · [Rule report](semantic/declared-rule-report-v0.1.schema.json) | Directory responsibility rules and findings |
| [Responsibility–Behavior](semantic/responsibility-behavior-v0.1.schema.json) | Non-scoring syntax/role observations |

These semantic companions do not modify frozen CCG v0.1 or prove actual
runtime behavior.

---

## Future Areas
Create future contract areas **only after their contents are designed**.
`contracts/profile/` is **planned, not implemented**: it could validate
profile structure, but must not prescribe repository-specific policy values.
