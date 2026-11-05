<div align="center">
<h1>Semantic Architecture Contracts</h1>
<p><strong>Evidence-backed architecture descriptions and declared rules.</strong></p>
<p>Companion v0.1 · Non-scoring · Separate from CCG</p>
</div>

---

## Contract catalog
| Contract | Responsibility |
| :-- | :-- |
| [Architecture vocabulary v0.1](architecture-v0.1.vocabulary.json) | Entity kinds, typed relation endpoints, assurance types, assessment states and unsupported dimensions |
| [Architecture report v0.1](architecture-v0.1.schema.json) | Evidence-based entities, relations, assessments and explicitly unassessed dimensions |
| [Declared rule policy v0.1](declared-rule-policy-v0.1.schema.json) | Scoped directory responsibilities, policy revision and explicit exceptions |
| [Declared rule report v0.1](declared-rule-report-v0.1.schema.json) | Source-backed evaluation of declared architecture rules |
| [Responsibility–Behavior v0.1](responsibility-behavior-v0.1.schema.json) | Independent, non-scoring imported-API syntax observations and role-placement review |

## Validation & boundaries
- JSON Schema defines report shape. **Graph referential integrity** and
  vocabulary domain/range correctness also require the ground-truth semantic
  tests; schema validity alone is insufficient.
- These companions **do not modify CCG v0.1**. Repository-specific policies
  belong under [`profiles/`](../../profiles/) or are supplied by callers.
- An ontology relation, declared responsibility or imported-API observation
  **does not prove actual runtime behavior, semantic correctness or quality
  PASS**. Unsupported dimensions remain explicit.

See the [contract catalog](../README.md) and
[architecture semantics overview](../../docs/semantic-architecture-ontology.md)
for the relationship to CCG and codeQA evaluation.
