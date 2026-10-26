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

Consumer-side `SCOPED_GATE_ALLOW` now requires a non-empty set of independently
admitted Gate requirement decisions, each with a valid evidence digest and
`PASS` status; a caller-created `GateDecision(PASS, ALLOW)` with no evidence
requirements, or an unadmitted requirement, is reported as `BLOCK` with
`GATE_REQUIREMENTS_OR_ADMITTED_EVIDENCE_MISSING`. This is an additive, stricter
consumer safeguard and **does not** replace the original Gate policy validator
or authenticate the caller-supplied receipt. Production merge authorization
remains false for every case.

The consumer additionally requires the caller's exact snapshot identity to
have the form `git:<owner>/<repo>@<40-hex-source-sha>` and to match the
separately pinned source SHA. A coherent forged receipt for a stale SHA or an
opaque snapshot cannot yield `SCOPED_GATE_ALLOW` or `FIXTURE_ONLY`.
This is only **syntactic revision binding**: it does not authenticate GitHub,
prove the source was checked out by the runner, or establish deployed binary
identity. Two negative regression tests exercise the previously unguarded
cross-field mismatch.

## Read-only GitHub run/source relationship witness (2026-10-26)

The pinned Dafny consumer CI now requires `actions: read` and
`contents: read` **only**. Its bounded, fixed-host GitHub REST GETs
independently retrieve the current workflow run and exact checked-out commit.
For PR CI, the synthetic merge commit's second parent must match the run's
actual raw PR head, and the run must reference the same PR number, repository,
workflow, run attempt and event. Push/manual runs instead require direct
commit-head identity. Forged run IDs, workflow paths, repositories, merge
parents, PR heads, attempts and unsafe refs fail closed. The resulting
`remote_run_attestation` field has
`GITHUB_API_RUN_SOURCE_RELATIONSHIP_VERIFIED` **only after real API readback**.

This is stronger than a self-consistent caller receipt, but **does not
authenticate the Actions runner, uploaded artifact bytes, solver binary,
compiler semantics, requirements applicability, deployment identity, or
human production merge policy**. The existing typed #98/#99 Gate consumer
still reports `CALLER_PINNED_RECEIPT_ONLY` at its own contract level;
the CI wrapper adds separately scoped GitHub metadata. The general Formal
Gate remains `UNKNOWN/BLOCK`, generated fixture
`ALLOW_FIXTURE_ONLY`, and `production_merge_authorized=false`.
No cross-repository write capability or production rollout is enabled.

## CI receipt repository identity guard (incremental #121)

The caller-supplied `ci_run_url` must now refer to the **same exact GitHub
owner/repository** named by the canonical `git:owner/repo@SHA` snapshot.
A syntactically plausible run URL from a different repository, or a dot-segment
repository path, blocks even a scoped Gate decision. This prevents a
cross-repository URL from being presented as a source-local receipt; it is
still **not** an authenticated GitHub run check. Independent read-only remote
attestation remains a separate downstream step. The production merge flag
remains `false` regardless of receipt content or fixture verification.
