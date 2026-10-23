# QA exchange contracts v0.1

- [Result](result-v0.1.schema.json): versioned evidence, source scope,
  coverage, measured-rule outcomes and unsupported principles.
- [Quality Delta](delta-v0.1.schema.json): descriptive review-count changes
  only after strict comparison preconditions.

See [normative QA contract semantics](../../docs/contracts/qa-result-0.1.md).
The JSON Schema is structural; the separate fail-closed semantic validator
must also be called. These artifacts never redefine CCG v0.1.
