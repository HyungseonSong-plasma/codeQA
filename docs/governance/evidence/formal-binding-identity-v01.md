# Formal proof-to-implementation binding: bounded identity milestone (#102)

This is an additive early implementation, **not** final #102 acceptance.

`codeqa.evaluation.formal_binding` parses an exact, typed, versioned
`FormalBinding` and verifies independent SHA-256 identities of specification,
generated artifact, and deployed artifact. The generated-code variant requires
generated and deployed hashes to match; an independently supplied toolchain,
build-configuration and attestation identity are also required. Manual
translations are always `NOT_EVALUATED`.

The checker returns `IDENTITY_MATCH`, `BINDING_BROKEN`, or `NOT_EVALUATED`.
**Even `IDENTITY_MATCH` is not mathematical equivalence, Dafny proof
validation, compiler soundness, or authorization to bypass #99's formal
implementation Gate.** The result intentionally says
`SEMANTIC_PRESERVATION_NOT_ESTABLISHED`.

The current gate `FORMAL_IMPLEMENTATION_VERIFIED` remains UNKNOWN/BLOCK until
verified proof obligations, trusted compiler/codegen provenance, deployment
equivalence and pinned real verifier CI are connected and independently
reviewed. See #102 for the remaining acceptance obligations.

Adversarial tests include unchanged specification with modified deployed
implementation, wrong generated artifact, missing trusted provenance,
manual translation, changed toolchain/configuration, missing properties and
malformed source paths.

No CCG/QA Result/Delta/Naming v0.1 semantics change.

## Canonical artifact path identity

Binding artifact paths are strictly repository-relative and must use one
canonical slash-separated spelling. Empty, `.`, or `..` path components,
backslashes and ASCII control characters are rejected for **every role**
(specification, generated and deployed). Caller-provided SHA-256 values alone
cannot resolve noncanonical source identity. The checker remains
identity-only and never converts this validation into implementation proof.
