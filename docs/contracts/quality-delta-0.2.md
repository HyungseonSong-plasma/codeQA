# Evidence-aware Quality Delta v0.2 (#40)

**Versioned opt-in extension.** Frozen QA Result and Delta v0.1 schemas/APIs remain
unchanged. V0.1 compares strict review counts. This v0.2 extension compares
separately declared metric values, review flags, known source subjects and
compatible denominators. No global P8 quality score is introduced.

## Normative data

- `contracts/qa/metric-snapshot-v0.2.schema.json`, registered as
  `metric_snapshot_v02_schema`: immutable source commit, caller-supplied
  source bytes SHA-256, source-file parse coverage, and versioned rule
  identity, engine/version, profile fingerprint, metric name/unit, explicit
  denominator, concrete evidence IDs and lines, known limitations and
  `MEASURED` / `LIMITED` / `NOT_EVALUATED` scope.
- `contracts/qa/source-change-v0.2.schema.json`, registered as
  `source_change_v02_schema`: distinct source commit IDs and explicit
  old path/new path plus both actual SHA-256 hashes for each accepted rename.
- `contracts/qa/delta-v0.2.schema.json`, registered as `qa_delta_v02_schema`:
  per-rule `COMPARABLE` or `NOT_COMPARABLE` with detailed reasons, measured sums,
  review counts, signed descriptive deltas and matched/added/removed subjects.

Caller/Samuel owns immutable Git acquisition, source inventory and any GitHub
mutations. The new snapshot converter SHA-256 hashes supplied source text and
checks the old QA Result path/snapshot identity. It cannot independently
certify that caller-owned commit IDs correspond to those bytes.

## Fail-closed comparability

1. Both snapshots must be from the **same repository** at distinct immutable
   full SHA revisions; source-selection graphs must be consistent. A cross-
   repository comparison is rejected, not given a regression status.
2. Selected file paths must match, or be normalized by a caller-provided
   exact path mapping whose original/candidate file hashes both match.
   Similar filenames or symbols are **not** sufficient to infer a rename.
3. Both analyzed-path coverages must be `complete`. This means complete
   parsing of *selected inputs*, never complete repository or runtime analysis.
4. Comparable rules must agree on rule ID/version, principle, engine/version,
   full profile fingerprint, metric name/unit, and denominator kind/**value**.
   Changed denominators are not silently interpreted as equal populations.
5. Each rule must have genuinely `MEASURED` evidence with no unresolved gaps.
   Missing, omitted, syntax-unsupported or limited companion capabilities
   produce `NOT_COMPARABLE`, never a fabricated zero.
6. Declared source-relative path plus lexical subject key (without line number)
   is used to match **within the same path**. An explicit verified rename
   can relocate the path. Line relocation does not fabricate an added finding.
   Function rename or runtime identity is **not inferred**.
7. If all selected file SHA-256s are unchanged but normalized metrics differ,
   the rule is incompatible (`unchanged_source_bytes_conflicting_metrics`).
8. Compatible observations can be `MATCHED`, `ADDED` or `REMOVED`. Raw
   metric sums and review counts remain **descriptive candidates**, not proof
   of defects, regressions, safe changes or P8 design validity.

Rule-specific incompatibility is surfaced independently, so a v0.2 result
can be `PARTIAL` without manufacturing unsupported metrics.

## Existing evaluator companion adapters

`src/codeqa/evaluation/quality_delta_companions.py` provides explicit
normalization from real, opt-in, typed evaluator reports:

- `dependency_metric_rule`: selected-file static fan-out and unknown import
  limitations; **not** runtime coupling.
- `complexity_metric_rules`: function cyclomatic *proxy* and nesting, with
  unsupported syntax preserved.
- `duplication_metric_rule`: normalized token duplication fraction, with
  explicit eligible-token denominator and excluded-block scope.
- `architecture_metric_rule`: explicitly declared policy-violation witnesses
  and versioned policy fingerprint; unassessed architecture remains unknown.

Each one retains its producer, metric unit, profile and actual limitations.
They can be passed as `companions=...` to
`metric_snapshot_from_qa_result`. Missing/unselected companions remain
unsupported rather than silently treated as passing rules.

### Minimal usage

~~~python
from codeqa.evaluation.quality_delta_v02 import (
    metric_snapshot_from_qa_result, build_source_change_manifest,
    compare_metric_snapshots,
)
before = metric_snapshot_from_qa_result(
    old_qa_v01, old_source_text, repository="owner/repo", commit_sha=old_sha,
    result_schema=qa_schema_v01, snapshot_schema=metric_schema_v02,
    companions=tuple(old_companions),
)
after = metric_snapshot_from_qa_result(
    new_qa_v01, new_source_text, repository="owner/repo", commit_sha=new_sha,
    result_schema=qa_schema_v01, snapshot_schema=metric_schema_v02,
    companions=tuple(new_companions),
)
manifest = build_source_change_manifest(
    before, after, renames=(("old/path.py", "new/path.py"),),
)
delta = compare_metric_snapshots(
    before, after, manifest, snapshot_schema=metric_schema_v02,
    change_schema=change_schema_v02, delta_schema=delta_schema_v02,
)
~~~

`tests/test_quality_delta_v02.py` checks actual source-backed Mechanical
evidence, available Dependency/Complexity/Duplication companions, exact
renames, line moves, missing support, identical bytes with conflicting
observations, profile/engine/unit/denominator drift, partial parsing, cross-
repository rejection, pinned Samuel/MOOSE fixtures and deterministic JSON.
The standalone v0.1 API and schemas are regression-tested unchanged.
