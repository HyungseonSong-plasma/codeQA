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
