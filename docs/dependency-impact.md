# Static dependency correspondence and change impact v0.1

The existing Python analysis Pipeline now returns a companion `dependencies`
graph without altering **CCG v0.1** or Mechanical QA's rule decisions.

```python
from codeqa.pipeline.python import analyze_python
from codeqa.evaluation.impact import analyze_change_impact

analysis = analyze_python(
    pinned_sources,
    snapshot_id=pinned_source_revision,
    ccg_schema=ccg_schema,
    mechanical_profile=mechanical_profile,
)
report = analyze_change_impact(
    analysis.dependencies, ["src/codeqa/core/graph.py"],
)
print(report.to_document())
```

All inputs are in-memory snapshots. **Neither adapter, evaluation nor pipeline
reads Git, filesystem trees, or performs external orchestration.**

## Evidence and limits

- Python AST `import x`, `from x import y` and relative imports are mapped
  to a source path **only if one exactly matching module exists in the
  analyzed snapshot**. This is syntactic module-path correspondence, **not**
  proof of runtime module loading or symbol identity.
- `from package import member` maps to the package's `__init__.py`, if
  present; it **does not guess** that `member` is a Python submodule.
- Conditional/nested imports are retained but explicitly marked
  `conditional_or_deferred`. No import observation claims actual execution.
- Ambiguous module names, imports outside the snapshot, excessive relative
  traversal and recognized dynamic import calls remain **unknown** with
  explicit reasons. Dynamic code and framework-specific dependency injection
  can escape detection entirely. No false `resolved` edges are added to CCG.
- Files without importable module paths (e.g. `.github/scripts/...`) may
  still import indexed modules via absolute syntax.
- The source-root mapping recognizes `src/` layout and repository-root
  Python paths. Different import systems, editable installs, namespace
  package resolution, `sys.path` changes, import hooks and module caching
  are **not** modeled.
- Coverage is inherited from CCG. Unprocessed paths and requested changed
  files outside analyzed coverage are listed explicitly.

## Change impact

The pure `analyze_change_impact()` walks **reverse static import links**,
reporting direct dependents and transitive dependents with shortest witness
chains. Multiple changed paths are seeded together; cycles are safe. A result
is marked `STATIC_POTENTIAL_ONLY`: listed files have observed potential
import paths to changed files, **not proof that runtime propagation occurs**.
Conditional imports may never execute; dynamic dependencies may be missed.
The result is neither an exact lower nor an exact upper bound on runtime
impact. Unlisted files **cannot be certified unaffected**, and the output
must not be used as a safe test-selection filter.

`unknown_dependency_sources`, `untracked_changed_paths`, and
`unprocessed_paths` disclose limits instead of silently declaring safety.

Quality `status` and `analysis_status` remain independent of these new
diagnostics. Existing Mechanical Profile thresholds and old CCG facts are
preserved. Adding static import paths is **not** evidence of higher code
quality or true runtime coupling reduction.

See [self-audit](self-audit.md) for automatic codeQA source ranking and the
reproducible, SHA-pinned JSON output.
