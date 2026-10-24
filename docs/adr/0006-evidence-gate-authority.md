# ADR 0006 — Evidence admission and policy authorization are separate

**Status:** Adopted for opt-in Gate v0.1, 2026-10-24. **Issue:** #99.

## Decision
- Maintain frozen CCG v0.1 / QA Result/Delta and Naming contracts. Add an
  independent registered `evidence-gate-v0.1.schema.json` policy contract
  and source-scoped, three-valued Gate evaluator.
- Require **independent** policy fingerprint, immutable source manifest and
  snapshot, tool identity, exact raw artifact and #98 evidence admission at
  the point of each Gate decision. A stale or untrusted Admission object does
  not authorize reuse.
- Restrict policy syntax to exact files and anchored directory prefixes;
  validated conjunction of Semgrep no HIGH findings, Pyright no ERROR
  diagnostics and guarded Dafny implementation verification. The formal
  predicate remains unknown until #102 binds proof to deployed artifact.
- Keep execution/coverage failure distinct from proven violation:
  PASS requires all mandatory criteria; known admitted violation is FAIL;
  everything else is UNKNOWN; only PASS yields eligibility to authorize.
- Rule/path exception requires an explicit authorized policy fingerprint,
  reviewer/ticket/reason/expiry. No exceptions waive incomplete tool runs.
- **No** generic eval/exec, custom Turing-complete DSL, real code or GitHub
  mutation; avoid committing to Rego/CEL until observed scale warrants it.
  Document tradeoffs in `docs/evidence-gate-v01.md`.

## Rationale
Empty findings are not evidence of complete execution. Native tool exit codes
vary; #98 admissibility needs pinned identity and #100 real tool-classifier
conformance. Conflating a Dafny specification proof with an actual runtime
implementation would create false PASS.

## Required verification
Independent policy/source/tool identity mismatch, OOM/timeout, absent tool,
unsupported scope, rule-set drift, expired waiver, overlapping requirements
and missing proof binding must all block authorization. Determinism is tested.

## Future boundary
OPA/CEL adoption, stronger signed approvals, multi-run evidence federation,
formal binding (#102) and real external tools (#100) are independent work,
not silently implied by this Gate.
