# Scoped Authority Propagation Audit v0.1 (#121)

This additive read-only consumer audit composes **existing**, independently
versioned `GateDecision` (`ALLOW|BLOCK`) and
`GeneratedFixtureDecision` (`ALLOW_FIXTURE_ONLY|BLOCK`). It does not
replace, rename or broaden either Gate contract. The caller must independently
pin the expected snapshot, policy SHA-256, source Git SHA and receipt.

The receipt contains a canonical decision-byte digest, exact producer, policy,
snapshot, source SHA and a GitHub Actions run reference. A syntactically valid
run URL or a self-provided receipt is **not** independent evidence that a
workflow executed or that it checked the actual deployed source. The result's
`evidence_level` is therefore `CALLER_PINNED_RECEIPT_ONLY_NOT_INDEPENDENT_CI_VERIFICATION`.
The caller must still read actual exact-head CI and independently approve
policies. Missing or mismatched receipt data produces `BLOCK`.

Even a correctly pinned scoped Gate `ALLOW` yields only
`SCOPED_GATE_ALLOW`, never production merge authorization. A successful
Dafny generated fixture yields `FIXTURE_ONLY`, never semantic preservation
or production authorization. The audit's `production_merge_authorized` is
always false by design. Unsupported P1–P8 principles and unverified consumers
remain NOT_EVALUATED. No automatic PR merge, source rewrite or DB migration.

The unit tests include forged issuer, replayed decision digest, missing CI
receipt, unknown Gate, mismatched policy/source, invalid CI link and fixture
promotion negatives. This is the first boundary-validation milestone only:
**actual CI artifact readback, independent source-to-deployment binding and
human-reviewed Formal soundness are still required by #121 and #102**.

## Real Dafny receipt consumer round-trip (incremental CI witness)

The pinned real Dafny Actions workflow now invokes
`.github/scripts/authority_consumer_smoke.py` **after** generating its
`formal-evidence.json`. The consumer reconstructs typed Gate/fixture decisions
from serialized JSON, checks exact snapshot SHA and lossless serialization,
then requires the production/general Gate to remain `UNKNOWN/BLOCK` while
the generated fixture stays `PASS/ALLOW_FIXTURE_ONLY`. It writes
`authority-consumer-audit.json` into the same uploaded workflow artifact.

This is a real producer→JSON→consumer path on an actually executed pinned
Dafny verifier, not merely an isolated hand-constructed unit fixture. However
the supplied GitHub run ID is **not** a remote API readback or a cryptographic
attestation. The result's authority is explicitly
`CALLER_SUPPLIED_RUN_CONTEXT_NOT_REMOTE_ATTESTATION`. Independent CI readback,
review of the actual deployed target and human production policy approval
remain necessary. No general Gate `ALLOW` is inferred from fixture success.
