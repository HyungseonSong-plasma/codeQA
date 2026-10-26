# Typed source-proof receipt v0.1 — #102

The additive `codeqa.evaluation.formal_proof_receipt` layer audits a typed
#98 `ExternalEvidence` proof result against independently selected source,
snapshot, verifier/tool configuration, rule IDs, obligation IDs, accepted
assumptions, raw Dafny output and optionally a pinned solver identity.

`FormalProofEvidence.status` is one of `SOURCE_RECEIPT_CONSISTENT`,
`NOT_EVALUATED`, or `BLOCK`. Its scope is always
`VERIFIED_SPECIFICATION_ONLY`; `implementation_authorization` is **always
`BLOCK`**. A source-proof receipt does not establish compiler/codegen
semantic preservation, deployment provenance, real product requirements or
soundness of trusted axioms.

## Observed vs asserted tool provenance

`ToolIdentity` is the pinned verifier identity from #98. A separate
`SolverIdentity` records name, version and binary SHA-256 only when these
facts are supplied. Both observed and independently expected solver identities
must match before the source-receipt consistency status can be reached.
**These objects are caller-supplied and not cryptographically authenticated by
the module.** A trusted CI runner or independently verified external receipt
is still required to establish that a specific solver actually executed.

The real pinned Dafny 4.11.0 workflow now emits
`typed_formal_proof_receipt` within `formal-evidence.json`. It intentionally
reports `NOT_EVALUATED` with
`SOLVER_PROVENANCE_NOT_EVALUATED`: the current pinned archive, CLI version
and raw verifier stdout do not independently attest the solver executable,
its exact version and its invocation options. It must not invent this missing
witness. The existing separate generated fixture Gate can still report
`ALLOW_FIXTURE_ONLY` for its **narrowly defined** controlled fixture, while
the production formal Gate remains `UNKNOWN/BLOCK`.

## Fail-closed regression scope

`tests/test_formal_proof_receipt.py` covers a matching source-only
synthetic receipt, missing or mismatched solver, source/tool drift, forged or
ambiguous verifier summaries, nonzero/crashed verifier, timeout, absent
obligation, unaccepted assumptions, counterexamples and absent raw artifact.
The pinned Dafny Actions workflow exercises the same code on a real upstream
verifier and retains the original positive generated fixture and mutation
negative controls.

**Still open for #102:** independently attested solver/compiler/runtime and
transformation chain, explicit property-to-product requirement applicability,
signed target/deployment identity, positive production implementation Gate
and human approval. A matching source hash is byte identity, not a semantic
equivalence proof. No source/target code-write policy is changed.
