# External Evidence Envelope v0.1 and admissibility

**Status:** additive opt-in contract, Issue #98. **Authority:** registered JSON
Schema `external_evidence_envelope_schema` and the semantic validator in
`codeqa.core.external_evidence`; see ADR 0005.

## Why separate it from CCG and QA Result

The existing CCG v0.1 graph records source-parse observations, and public QA
Result v0.1 describes specific measured quality rules. Neither is an external
execution receipt nor a proof that a production implementation satisfies a
formal specification. Do not reinterpret existing QA `PASS` as a source-wide
clearance or mix confidence-like fields across unrelated tools.

This opt-in envelope has independent version `0.1` and holds:

- Immutable caller-attested `snapshot_id`; independently supplied expected
  file SHA-256 map and tool/config/ruleset identity are required for **admission**.
- Tool binary digest, version, adapter version, command/config digest, ruleset
  digest and exit-code classifier identity. **Never infer a successful run from
  exit code 0 or nonzero alone**; the adapter classifier has tool/version/mode
  semantics and is trusted only when its identity matches caller expectations.
- Explicit expected/scanned file paths and SHA-256 digests, skipped paths,
  parse errors and required/evaluated rule IDs. Equal *counts* are not proof
  of coverage. A reported scan manifest is an **attestation** from the tool
  adapter, not independent proof that a third-party tool scanned every file.
- Raw artifact URI (opaque, never opened by Core), format and digest. The
  caller must supply the actual bytes for independent hashing. Retain native
  reports, counterexamples and logs in caller-controlled immutable storage;
  the typed record is *not* a lossy replacement.
- A typed list of `STATIC_FINDING`, `TYPECHECK_DIAGNOSTIC`, and
  `FORMAL_PROOF_RESULT` observations. Tool-native statuses and proof
  assumptions are retained rather than normalized to a universal PASS,
  confidence or semantic correctness score.

## Validation and three admissibility outcomes

First, `parse_external_evidence(document, schema)` checks a strict, registered
JSON Schema plus duplicate/path/reference invariants and returns an immutable
Python DTO. Invalid structural input raises `ExternalEvidenceError`. The
caller MUST fail closed if parsing raises; this API is not a Gate decision.

Second, `assess_external_evidence(envelope, ...)` compares independently
declared expectations (source snapshot identity, exact path-to-digest map,
complete tool/config identity, required rules, raw artifact bytes) with
the record. Returns:

| Admission | Meaning | Policy implications |
| --- | --- | --- |
| `ADMISSIBLE` | This typed observation has complete asserted coverage and valid independent identity/artifact checks | May be passed to a separately versioned rule-specific Policy Gate; **not** a clean PASS |
| `INADMISSIBLE` | A contradiction exists: wrong source/tool/ruleset/artifact digest, foreign observation or stale snapshot | Reject this evidence for authorization |
| `INDETERMINATE` | Execution/scan incomplete, required rule missing, artifact or trusted expectation unavailable, or proof binding not established | Block unconditional authorization; do not infer absent findings |

`retained_observations` counts concrete observations even on a failed run:
a true finding is not erased by a later timeout. Rule-specific diagnosis
requires the separate #99 Gate. This module never merges/blocks PRs directly.

### Formal proof boundary

A `FORMAL_PROOF_RESULT` can represent a verification result for a *specific
specification* with declared assumptions and artifact identity.
The `purpose="IMPLEMENTATION_PROOF"` admission path **always** remains
`INDETERMINATE` in this version until #102 provides separately attested
proof-to-implementation / generated-code / deployment binding. A Dafny
`VERIFIED` record for `spec.dfy` does **not** certify hand-translated
`engine.py`. Hash equality proves bytes, not semantic preservation.

### Tool execution boundary

Some tools report genuine findings through a nonzero exit code. An explicitly
pinned adapter must interpret native codes, interrupted output, parser and
configuration errors and report `execution.exit_classification`; Core does
not guess tool-specific meanings. A matching classifier identity is necessary
but does not by itself guarantee the adapter ran honestly; integration tests
and provenance attestation are owned by #100 and the relevant SDK/compilers.

## Example API

```python
from codeqa.infrastructure.resources import ResourceRegistry
from codeqa.core.external_evidence import (
    ToolIdentity, parse_external_evidence, assess_external_evidence,
)

schema = ResourceRegistry(repo_root).load_json("external_evidence_envelope_schema")
typed = parse_external_evidence(adapter_document, schema)
result = assess_external_evidence(
    typed,
    expected_snapshot_id=trusted_snapshot_id,
    expected_files=trusted_path_digest_map,
    expected_tool=trusted_tool_identity,  # ToolIdentity
    expected_rules=trusted_required_rules,
    raw_artifact=actual_report_bytes,
)
# A future #99 Gate may evaluate the findings only when admissible.
```

## Trust assumptions and non-goals

The caller owns authentic Git snapshot acquisition and selected sources; this
API cannot independently prove the caller's assertions. The untrusted
`raw_artifact.uri` is never dereferenced by Core. It does not execute scanned
code, tool binaries or untrusted YAML/policy expressions. It does not validate
a tool's native JSON/SARIF semantics: that belongs to the pinned adapter.
No new CCG edge, runtime inference or code mutation occurs.

Future #99 Policy Gate and #100 Semgrep adapter use this contract but remain
**separate**. CI semantics and adversarial fixtures must be reviewed before
relying on any external analyzer result to authorize merges.
