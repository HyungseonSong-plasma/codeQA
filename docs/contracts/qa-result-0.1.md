# QA Result and Quality Delta v0.1

**Status:** versioned language-independent exchange contracts. **Owner:** Issue #28.

- Result: `contracts/qa/result-v0.1.schema.json`
  (`urn:codeqa:qa:result:v0.1`, logical ID `qa_result_schema`).
- Delta: `contracts/qa/delta-v0.1.schema.json`
  (`urn:codeqa:qa:delta:v0.1`, logical ID `qa_delta_schema`).
- Semantics: `codeqa.evaluation.qa_result`.

These are public **opt-in** schemas, not retroactive promises that the
existing `PythonAnalysis.to_document()` and `MechanicalReport.to_document()`
internal representations are frozen.

## Ownership, scope and verdict meaning

Samuel/chatgpt-operation owns acquiring immutable snapshots and any GitHub
mutation. Language adapters emit observed syntax-grounded CCG facts; the QA
result keeps **quality judgment separate**. The profile is explicit repository
data, not inferred from the repository name.

`PASS` means only that the declared rules, on the explicitly analyzed source
paths, produced no review-triggering measurements. It is **not** universal
P1–P8 success, proof of low coupling, run-time correctness, or a full-repository
quality certification. `REVIEW_REQUIRED` identifies a threshold heuristic,
not a demonstrated design defect. `NOT_EVALUATED` is preserved when evidence
is missing. `FAIL` is reserved by the schema but is not producible by the
current evidence semantics because no proven failure mechanism is defined.

Parse coverage (`complete` / `partial` / `none`) is independent of rule
verdict and `analysis.status` (`COMPLETE` / `LIMITED` / `NONE`). In particular,
the existing Mechanical v0.1 behavior of scoped `PASS` on successfully parsed
files remains possible with `coverage.status=partial` and
`analysis.status=LIMITED`. A consumer MUST NOT present that as a full audit.

## Required report identity and observations

| Field | Meaning |
| --- | --- |
| `schema_version` | Frozen v0.1 exchange shape. |
| `snapshot.id` | Caller-supplied immutable input identity, not self-certified by codeQA. |
| `engine.id/version` | Measurer identity and implementation version. |
| `profile.id/fingerprint` | Human ID and SHA-256 of canonical complete threshold configuration. Equal IDs alone are insufficient for comparisons. |
| `scope.meaning` | Always `analyzed_paths_only` in v0.1. |
| `coverage` | Actual analyzed and unprocessed source paths, status and reasons. |
| `analysis.status/limitations` | Independently reported evidence completeness and explicit limitations. |
| `verdict.status/scope` | Aggregate of scoped rule outcomes; never a hidden global score. |
| `rules[]` | Rule/version/principle, metric name/unit, rule verdict, evidence references, limitations. |
| `evidence[]` | Deterministic identity, source node/location, numeric measured value/unit, threshold comparison, source method and rule ID. |
| `unsupported_rules[]` | Explicit unsupported P1–P8 principles and reasons. |

JSON Schema validation **alone is insufficient**. The public validator checks
unique identities; evidence references, paths, locations and cross-links;
non-finite metric rejection; unit consistency; observed value versus strict
threshold; scope accounting; coherent `PASS`/`REVIEW_REQUIRED`/`NOT_EVALUATED`;
missing provenance; and coverage contradictions. Every P1–P8 principle must
be either represented by a declared rule or explicitly listed unsupported.

## Current Python Mechanical v0.1 projection

The converter exports exactly two heuristics:

- `function_span_review` (P1) counts a source-observed function span in `line`.
- `outgoing_call_sites_review` (P3) counts syntax-observed `call_site` nodes.

P2 and P4–P8 are unsupported for this report, irrespective of other optional
non-scoring semantic companion layers. The converter derives locations and
function identities from the CCG and thresholds from an explicit Mechanical
profile, validating report consistency before producing a result. It does
not mutate the CCG, change internal reports or claim complete P1–P8 scoring.

~~~python
from codeqa.pipeline.python import analyze_python
from codeqa.evaluation.mechanical import MechanicalProfile
from codeqa.evaluation.qa_result import mechanical_to_qa_result, canonical_qa_json
from codeqa.infrastructure.resources import ResourceRegistry

resources = ResourceRegistry(codeqa_root)
profile = resources.load_json("mechanical_profile")
analysis = analyze_python(
    {"a.py": "def f():\n    pass\n"},
    snapshot_id="caller-verified-immutable-snapshot",
    ccg_schema=resources.load_json("ccg_schema"),
    mechanical_profile=profile,
)
public = mechanical_to_qa_result(
    analysis.graph, analysis.quality, MechanicalProfile.from_mapping(profile),
    schema=resources.load_json("qa_result_schema"),
)
serialized = canonical_qa_json(public)
~~~

## Quality Delta v0.1

`compare_quality_delta(baseline,candidate,result_schema=...,delta_schema=...)`
computes only the signed **difference in counts of review-triggering
observations per rule**. It does not measure overall quality, defect reduction,
semantic improvement, or runtime behavior.

Comparison fails closed unless:

1. Snapshot IDs are distinct, caller-owned immutable identities.
2. Engine identity/version, profile ID **and fingerprint**, declared scope and
   every rule ID/version/principle/metric **name and unit** match.
3. Both have complete parsing of the exact same selected source-relative
   paths. This does not independently establish that the selected paths
   comprise the complete repository.
4. Both have `analysis.status=COMPLETE` with no limitations and no
   `NOT_EVALUATED` rule. Unsupported principle lists must match.
5. Both complete Result documents pass schema **and** semantic checks.

A missing, ambiguous or incomparable measurement is **not zero**. No
cross-version unit conversion, file heuristic matching or partial-coverage
fallback exists in this initial version.

## Reproducibility and limits

`tests/test_qa_result_contract.py` contains positive and adversarial
source-grounded executable fixtures, including stale provenance,
dangling/duplicate evidence, contradictory PASS, invented FAIL, partial
coverage, unavailable principles, unsafe source locations, incompatible
metrics/profiles/rules/engine IDs, NaN and stable canonical JSON.

The exact same schema version plus immutable input, profile and engine must
produce the same canonical JSON (no volatile timestamps). Old report APIs,
CCG v0.1 and Mechanical thresholds remain unchanged. Contract/CI PASS
does **not** establish complete universal source analysis or scientific
correctness.
