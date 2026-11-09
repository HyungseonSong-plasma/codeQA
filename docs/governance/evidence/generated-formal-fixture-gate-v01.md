# Restricted Dafny-generated fixture Gate v0.1 (#102)

**Purpose:** A separate, opt-in positive conformance Gate for a deliberately
controlled *Dafny-generated Python fixture*, not an implementation-proof Gate
for arbitrary existing source, real deployments or a production payment app.

## Explicit authority boundary

The existing public #99 policy predicate `FORMAL_IMPLEMENTATION_VERIFIED`
continues to return `UNKNOWN/BLOCK` for source-only Dafny evidence, even
when the test fixture receives a scoped PASS here. We intentionally do **not**
modify the frozen #98 External Evidence, #99 Gate or CCG v0.1 contracts.

`codeqa.evaluation.formal_generated_gate` defines a tightly restricted,
versioned data-only policy `GeneratedFixturePolicy(version="0.1")`. Its
`scope` accepts only `CONTROLLED_GENERATED_PYTHON_FIXTURE`. Any production
or manual-translation scope is rejected at parse time.

A positive outcome is precisely `PASS / ALLOW_FIXTURE_ONLY`. It says that,
under caller-attested CI/trust assumptions, all of the following match:

- Independently expected immutable source snapshot/path/SHA-256.
- Expected exact pinned Dafny tool binary/configuration and rule identities.
- Actual raw verifier bytes, `COMPLETED` exit code zero and a single
  nonzero-verified, zero-errors solver summary, accompanied by #98 admissible
  typed `FORMAL_PROOF_RESULT`.
- Exact enumerated requirement IDs, proof status `VERIFIED`, source digest,
  no counterexample, exact accepted declared trust assumptions.
- Typed #102 `GENERATED_CODE_MATCH` binding, source/specification SHA,
  expected toolchain/build configuration/attestation IDs, declared properties.
- Every expected Python source file by relative path and SHA-256, checked
  across generated output and a **temporary deployment fixture**. The
  source-tree manifest includes the complete Python package, not merely
  `__main__.py`.

All independently required values are part of the caller-selected policy,
not filled in by the untrusted verifier report. Missing or contradictory
evidence becomes `UNKNOWN / BLOCK`, with deterministic decision reasons.
A known runtime bug has **not** been proved by a digest mismatch; such a
mismatch only invalidates previously established identity.

## What a fixture PASS does not mean

A positive fixture Gate does not prove Dafny's source-to-Python translation
sound, validate the Python interpreter/stdlib, attest a real deployment
identity or establish semantic equivalence with manually written Python/C++.
It also does not authenticate GitHub workflow credentials, CI runners or
owner approval of a real payment specification.

In the current official workflow
`.github/workflows/pinned-dafny-formal.yml`, a hash-pinned upstream
Dafny 4.11.0 release runs `verify`, a deliberate failing mutation,
`build --target:py`, and the generated Python program. The fixture manifest
pins the expected generated file set and accepted limitation/assumption
strings. This yields an inspectable `generated_fixture_gate` receipt in
`formal-evidence.json`, alongside the **still BLOCKED public formal Gate**.

Only fixture CI may interpret `ALLOW_FIXTURE_ONLY`. It must never be
translated to a generic merge/deploy `ALLOW`.

## Full production verification remains an independent design problem

Future full #102 acceptance requires trustworthy attestation of the *actual*
deployed binary or source and build provenance, a vetted transformation
correctness/trusted computing base assumption, evidence that the explicit
proof obligations adequately express product requirements, independent
review/approval, and production-specific negative controls. No human
review, compiler soundness theorem, runtime soundness theorem or independent
production deployment has been fabricated here.

**Tests:** `tests/test_generated_formal_fixture_gate_v01.py`, pinned real
Dafny job, existing #98/#99 tests and exact PR-head main workflows.
