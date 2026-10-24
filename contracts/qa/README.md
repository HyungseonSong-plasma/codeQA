# QA exchange contracts v0.1

- [Result](result-v0.1.schema.json): versioned evidence, source scope,
  coverage, measured-rule outcomes and unsupported principles.
- [Quality Delta](delta-v0.1.schema.json): descriptive review-count changes
  only after strict comparison preconditions.

[External Evidence Envelope v0.1](external-evidence-envelope-v0.1.schema.json)
is a **separate opt-in contract** for typed external analyzer results,
execution integrity and admission eligibility. It is not a QA verdict;
see [external evidence semantics](../../docs/external-evidence-v01.md)
and [ADR 0005](../../docs/adr/0005-external-evidence-admissibility.md).

See [normative QA contract semantics](../../docs/contracts/qa-result-0.1.md).
The JSON Schema is structural; the separate fail-closed semantic validator
must also be called. These artifacts never redefine CCG v0.1.
