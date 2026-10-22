# Reproducible codeQA self-audit

The [codeQA Self Audit](../.github/workflows/self-audit.yml) workflow runs the
existing Python Adapter → CCG Core → Mechanical Evaluator on codeQA's own tracked
Python sources at an exact Git commit. The runner is a composition script in
`.github/scripts/`, not a new repository-reading responsibility in Pipeline.

## Scopes

- **production**: `src/codeqa/**/*.py`; primary engineering code.
- **tests**: `tests/**/*.py`; analyzed separately to avoid skewing product findings.
- **all_python**: all tracked Python files, including fixtures and the runner.

Every result records the commit SHA, exact paths, CCG node/edge counts, parsing
coverage, unresolved references (including a per-kind breakdown), threshold
values, review findings, the separate `analysis_status` and
`analysis_limitations`, and diagnostics. The structured JSON is retained as
a workflow artifact. Historical results can be compared by pinned SHA.

`complete` means the supplied Python files parsed, **not** that all calls
were resolved. Non-Python files are outside the analyzed scope. Both measured
P1/P3 signals are heuristics rather than proof of violations; an overall P1–P8
quality judgment is not available. Quality `PASS` with analysis `LIMITED`
does **not** certify the full snapshot. The informational `self-audit` workflow
does not replace the required `layout` branch-protection check.

## Reproduction

On a clean checked-out Git SHA with Python 3.12+:

```bash
python3 -m pip install -e .
python3 .github/scripts/self_audit.py \
  --sha "$(git rev-parse HEAD)" \
  --output self-audit-report.json
```

## Refactor regression with fixed source SHA

The workflow also analyzes the immutable pre-refactor source tree at
`6a6676e70ed60f440cfc00a878f24ef6ee2b91a5` using the **currently
checked-out analyzer code**. This is separate from analyzing current HEAD.
`fixtures/analysis/self-audit-baseline.json` stores counts and verdict facts
observed by the original analyzer on that exact source snapshot (from the
historical main self-audit workflow). The regression checker requires
identical file, node, edge, unresolved-reference, review-finding and
lexical-link counts on that frozen input.

This isolates an analyzer refactor from changes in the subject repository.
It does not claim that fewer current-HEAD findings imply higher quality.
New non-scoring `call_metrics` are intentionally omitted from the historical
baseline because they did not exist in the earlier analyzer. Both current
and frozen-source reports are uploaded as artifacts.

## Dependency evidence and impact ranking

The self-audit now records observed source-to-target import pairs,
conditional/nested import observations, unknown imports by reason, and
ranked static reverse-import impact examples for product Python sources.
For `all_python`, dependent tests can be included when a statically
matching module import is present. Impact rankings are **lower bounds**:
dynamic imports, out-of-snapshot dependencies, test fixtures and runtime
dispatch are not exhaustively mapped. Rankings are not quality scores.
