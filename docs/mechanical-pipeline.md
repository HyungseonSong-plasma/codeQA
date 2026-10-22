# Mechanical QA v0.1 and Python analysis pipeline

The `codeqa.pipeline.python.analyze_python` function composes the Python
syntax Adapter, CCG v0.1 Core validation and limited mechanical evaluation.

```python
from codeqa.pipeline.python import analyze_python
from codeqa.infrastructure.resources import ResourceRegistry

registry = ResourceRegistry(codeqa_repository_root)
result = analyze_python(
    {"source.py": "def example():\n    pass\n"},
    snapshot_id="the-pinned-input-revision",
    ccg_schema=registry.load_json("ccg_schema"),
    mechanical_profile=registry.load_json("mechanical_profile"),
)
document = result.to_document()
```

Callers own **source acquisition and immutable snapshot identity**.
The Pipeline never imports source files, reads repository trees, runs code, or
performs GitHub mutation. External Samuel/David orchestration remains external.

## Current evidence-based signals

- **Function size**: measured line span against the explicit
  `max_function_lines` profile threshold. It is a review heuristic related to
  P1 (SRP), **not** proof of SRP violation.
- **Outgoing call sites**: count syntax-observed call sites in function/method
  scopes against `max_call_sites`. It is a review heuristic related to P3
  (low coupling), **not** proof of excessive coupling.
- **Quality `status`**: `REVIEW_REQUIRED` is produced only when a measured
  threshold is exceeded. `PASS` means that the two v0.1 heuristics were
  measured on *the analyzed subset* without a threshold finding.
  `NOT_EVALUATED` means that no function was available or required function
  evidence was missing. The evaluator never emits speculative `FAIL`.
- **Independent `analysis_status`**: `COMPLETE`, `LIMITED` or `NONE`.
  `LIMITED` covers unresolved relationships, partial parsing and missing
  function evidence, with exact reasons in `analysis_limitations`.
  `coverage_status` and `unresolved_edges` remain separately available.
- **Non-equivalence**: `status=PASS` together with
  `analysis_status=LIMITED` is allowed and **must not** be interpreted as
  whole-repository approval. Even `analysis_status=COMPLETE` means complete
  *for the currently modeled information*, not complete Python semantics.

Threshold signals still do not prove SRP or coupling defects. Full P1–P8
evaluation and a stable external Quality Report Contract remain unimplemented.

Policy values live in `profiles/` and are loaded through the logical
`mechanical_profile` ID. The report is currently an **internal Python
structure**, not yet a versioned external Quality Report Contract.

## Distinct call evidence (non-scoring)

Each function or method now has `call_metrics` in the internal report:

- `call_sites`: all syntactically observed call expressions (the existing
  `max_call_sites` rule retains its original threshold and meaning).
- `distinct_resolved_targets`: unique CCG target IDs backed by a resolved
  call edge. Multiple calls to one target count once.
- `unresolved_call_sites`: call expressions without a verified target.
- `distinct_unresolved_hints`: distinct observed callee expressions, which
  are **not** proven dependency identities.
- `external_dependencies`: `null` until cross-module identity can be
  established safely; do not read `null` as zero external dependencies.

The added evidence is diagnostic only. It neither changes the threshold rule
nor creates a new P3 coupling verdict. Existing `status` and
`analysis_status` have identical meanings to the prior release.
