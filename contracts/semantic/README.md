# Semantic Architecture Contracts

- `architecture-v0.1.vocabulary.json` declares entity kinds, typed relationship endpoints, assurance types, assessment states and unsupported dimensions.
- `architecture-v0.1.schema.json` validates the companion report; graph referential integrity and vocabulary domain/range correctness are verified in ground-truth tests.

CCG v0.1 stays independent and unchanged. Policies are repository-specific under `profiles/` or supplied by callers. No ontology relation establishes actual runtime behavior by itself.

- `responsibility-behavior-v0.1.schema.json` describes a separate,
  non-scoring syntax-observation and role-placement review report.
