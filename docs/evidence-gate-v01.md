# Evidence Policy Gate v0.1 (opt-in, #99)

**Authority:** `contracts/qa/evidence-gate-v0.1.schema.json` (registered as
`evidence_gate_schema`) plus `src/codeqa/evaluation/evidence_gate.py`.
This is **not** CCG/Mechanical/P1–P8 QA Result and does not authorize PR merges
or execute untrusted source code. See #98 for independently validated typed evidence.

## Deliberately bounded policy language

Instead of a new programming language, v0.1 accepts a strict **data-only**
JSON mapping. Requirements have one of three predicates:
`STATIC_NO_HIGH_FINDINGS` (pinned Semgrep), `TYPE_NO_ERRORS` (pinned Pyright),
or `FORMAL_IMPLEMENTATION_VERIFIED` (pinned Dafny; necessarily UNKNOWN until
#102 trusted proof-to-implementation binding exists).

A scope is an exact relative file path or anchored `directory/**`.
Every requirement must match a selected source. Requirements over overlapping
paths combine with **AND**; no hidden allow rule, implicit short-circuit PASS,
priority override or executable expression is supported. A separate approved,
fingerprinted policy is needed for exceptions.

```json
{
  "schema_version": "0.1",
  "policy_id": "repo.security.v0.1",
  "snapshot_id": "git:owner/repo@<immutable-revision>",
  "source_files": [
    {"path": "src/api/app.py", "sha256": "<actual-source-sha256>"}
  ],
  "requirements": [
    {
      "id": "api.semgrep",
      "scope": "src/api/**",
      "tool": {
        "name": "Semgrep", "version": "<pinned>",
        "binary_sha256": "<sha256>", "adapter_version": "<pinned>",
        "invocation_sha256": "<sha256>", "ruleset_sha256": "<sha256>",
        "exit_classifier": "<pinned-native-semantics>"
      },
      "rule_ids": ["security.check"],
      "predicate": "STATIC_NO_HIGH_FINDINGS",
      "exceptions": []
    }
  ]
}
```

The sample placeholders are not executable configuration; actual digests and
tool identities must be provided and pinned independently.

## Trust model

The caller **must** supply:
- An independently authorized **policy SHA-256** of the *canonical parsed
  policy document*, not a digest computed from an untrusted candidate alone.
- Immutable source snapshot identity and exact selected path-to-content digest
  mapping, independently acquired and attested by the orchestrator.
- For each required Gate ID, the typed #98 `ExternalEvidence` and its
  actual raw output bytes. The Gate recomputes #98 admission for each run against
  its own pinned tool identity, rule-set and expected scoped files. It **never**
  accepts a caller-provided `Admission=ADMISSIBLE` assertion.

A tool's reported successful run and exact scanned files are still statements
from a trusted/pinned adapter, not cryptographic proof that all targets were
analyzed. #100 owns independent real Semgrep coverage and exit-mode conformance.

The Gate does not infer a clean result from absent Findings unless the required
source/rule coverage, execution, raw artifact integrity, tool/config identity
and policy/snapshot identities are all admissible.

## Decision algebra

For a requirement:

- `PASS`: all expected identities/coverage are attested, required evidence
  admitted, and no unwaived finding violates the specific predicate.
- `FAIL`: at least one **admitted and non-waived** HIGH/CRITICAL static
  finding or ERROR type diagnostic contradicts the required predicate.
- `UNKNOWN`: evidence missing, incomplete, contradictory, source/tool/policy
  freshness mismatch or formal source binding unresolved.

Across requirements, the deterministic algebra is **FAIL > UNKNOWN > PASS**.
`authorization=ALLOW` occurs only on an overall PASS; all other outcomes
return `BLOCK`. UNKNOWN is *not* misreported as a verified software defect.

An observed finding is retained in #98 raw/typed evidence even after timeout,
but an unadmitted finding does not become independently proven. Rule trace
includes requirement ID, matched paths, admission, unknown reasons,
observed/waived violations, and content digest. No global quality score.

### Exceptions

A waiver requires exact selected source path, exact rule ID, ticket,
reviewer, reason and offset-aware expiry; it must be part of the authorized,
independently fingerprinted policy. Expired waivers no longer suppress
findings. Unscoped exceptions cannot repair missing Coverage, broken
admissibility or failed runs. A reviewer name in policy is **not**
cryptographic proof of real human authorization; the trusted policy authority
must separately control approval and digest pinning.

## External policy engine options

| Option | Assessment | v0.1 decision |
| --- | --- | --- |
| Restricted data-only typed policy in pure Python | Very small, deterministic, bounded trust surface; supports the three known predicates and strict conjunction | **Selected** for the minimal platform pilot; not a general DSL |
| OPA/Rego | Mature policy evaluation, strong audit ecosystem; introduces executable policy runtime, packaging/distribution and Rego conformance obligations | Defer to #99 follow-up/extension if complex cross-project policy justifies it |
| CEL | Compact embeddable expression evaluation; expression semantics, host bindings and cross-version portability still require independent review | Defer until simple declarations become insufficient |

This choice does not deny the benefits of OPA/CEL; it avoids premature new
infrastructure while still enabling a versioned decision contract. Future
policy languages must produce the same fail-closed three-valued semantics and
decision trace under adversarial inputs.

## Executable usage

```python
from codeqa.infrastructure.resources import ResourceRegistry
from codeqa.evaluation.evidence_gate import (
    EvidenceRun, parse_gate_policy, evaluate_gate,
)

schema = ResourceRegistry(repository_root).load_json("evidence_gate_schema")
policy = parse_gate_policy(independently_supplied_policy_doc, schema)
decision = evaluate_gate(
    policy,
    runs={"api.semgrep": EvidenceRun(typed_evidence, real_output_bytes)},
    expected_policy_sha256=trusted_policy_fingerprint,
    expected_snapshot_id=trusted_snapshot,
    expected_sources=trusted_source_sha256_by_path,
    evaluated_at=trusted_evaluation_timestamp,
)
# Only `decision.authorization == "ALLOW"` is eligible for future external
# merge/deployment policy; this library NEVER performs the action itself.
```

## Deferred

- Actual Semgrep binary execution, exit-code classifier and coverage attestation
  are #100; pinned real SDK/ORM and MOOSE tool semantics remain #92/#93.
- Formal implementation binding and trusted compiler/codegen chain are #102;
  standalone Dafny `VERIFIED` can never authorize production code here.
- Persistent CCG cache and transitive invalidation are #101.
- Complex exception precedence, external signed approval services or arbitrary
  Rego/CEL expressions require separate versioned reviews; no runtime eval.

**Regression:** `tests/test_evidence_gate_v01.py` includes overlapping policy
requirements, source and policy drift, no-result crash/OOM, nonzero type-error
exit, incomplete scan, stale rule and tool, explicit waiver and expiration,
unbound Dafny proof, scope ambiguity and deterministic decision serialization.
