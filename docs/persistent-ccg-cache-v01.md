# Persistent file-local CCG caching and conservative invalidation v0.1 (#101)

**Status:** opt-in, POSIX trusted-cache extension. **Safety boundary:** only
file-local syntax extraction is persistent. This is not an incremental
cross-file semantic interpreter, exact change-impact oracle, or automated
test selector. Existing CCG v0.1, QA Result, Naming and Delta are unchanged.

## Current implementation

`PythonAnalysisCache` already reuses caller-owned in-memory AST and
file-local CCG extraction facts keyed by `(path, SHA256(source))`.
All snapshot-wide bindings, dependency analysis, CCG validation, findings,
quality verdicts, source evidence and optional static impact recompute
on each call of `analyze_python`.

`PythonPersistentExtractionCache` in
`src/codeqa/adapters/python_persistent_cache.py` optionally saves **only**
the file-local `_Extract` node/edge dictionaries as canonical JSON bytes.
No AST/pickle, dangerous import/execution, network, user code mutation,
cross-file graph or QA result is persisted. Every analysis still parses its
actual sources and rebuilds ALL snapshot-wide semantics.

### Cache keys and provenance

The persistent key fingerprints:

- Explicit caller namespace (repository/branch or workload context);
- Relative POSIX file path and SHA-256 of exact source UTF-8 bytes;
- Current Python interpreter/grammar implementation and version;
- SHA-256 of current extraction + lexical binding + parser source modules;
- File-local extraction format version `0.1`.

A record stores the provenance again plus a SHA-256 checksum of canonical
JSON. Loading rejects wrong namespace, producer, path, source SHA, checksum,
missing/oversized/corrupt data, unsafe paths and symlinks, with cold extraction
fallback. No trust is granted to a stale source or merely matching filename.

This is **integrity, not authenticity**: a malicious actor allowed to write
both a cache payload and checksum can forge records. A caller MUST provide a
trusted, isolated cache directory and avoid consuming untrusted caches from
PRs or other tenants. The API does not cryptographically sign data.

POSIX `fcntl.flock` guards load/save/eviction; atomic temporary writes +
`os.replace` avoid partial records. Storage is capacity-bounded by
`max_entries` and per-entry maximum bytes. Unsupported platforms fail
explicitly rather than silently dropping synchronization semantics.

## Usage

```python
from pathlib import Path
from codeqa.adapters.python_persistent_cache import PythonPersistentExtractionCache
from codeqa.adapters.python_snapshot import PythonAnalysisCache
from codeqa.pipeline.python import analyze_python
from codeqa.evaluation.incremental import plan_python_invalidation

disk = PythonPersistentExtractionCache(
    Path("/trusted/workspace/cache"), namespace="owner/repo:feature",
    max_entries=512,
)
cache = PythonAnalysisCache()
disk.hydrate(cache, selected_source_texts)
analysis = analyze_python(
    selected_source_texts, snapshot_id=immutable_snapshot_sha,
    ccg_schema=ccg_schema, mechanical_profile=mechanical_profile,
    cache=cache, changed_paths=("src/mymodule.py",),
)
disk.save(cache)
plan = plan_python_invalidation(
    analysis.dependencies, ("src/mymodule.py",),
    policy_changed=False, toolchain_changed=False,
)
```

Cache hit and parse work counters remain distinct: disk extraction reuse
does **not** avoid the per-run Python AST parse needed by other pipeline
stages. Benchmarks therefore must measure actual CPU/memory/I/O separately.

## Invalidation policy

`plan_python_invalidation` reports potential reverse-import dependents
but **never** uses their absence to skip snapshot-wide semantic evaluation.
The always-present `STATIC_GRAPH_NOT_RUNTIME_DEPENDENCY_UPPER_BOUND`
reason documents that static imports are not a closed-world runtime proof.

`FULL_SNAPSHOT` is selected on any observed unresolved or dynamic import,
untracked/removed input, partial parse, changed source selection, parser,
policy, SDK/toolchain, compiler/macro/template context. Otherwise the plan
reports `LOCAL_EXTRACTION_REUSE_FULL_SEMANTICS`:
unchanged source files may safely reuse file-local facts, **while the entire
selected snapshot's semantic/QA relationships are rebuilt**.

C++/MOOSE build-target dependency metadata is not yet pinned or verified
(#93). In particular this plan CANNOT authorize per-translation-unit
selective source analysis or infer a safe compiler invalidation boundary.
Relevant compiler/source changes require a conservative full fallback.

External Semgrep or Dafny Evidence (#98/#100/#102) is never cached as a
file-local extraction fact; freshness/source binding and policy fingerprints
are checked independently at evidence admission/Gate time (#99).

## Oracle and benchmark

- `tests/test_persistent_ccg_cache_v01.py` compares byte-equivalent
  semantic documents from full/no-cache versus persistent-warm analyses,
  deliberately excluding **work-counter** fields only.
- Seeded mutations cover source changes, imports, new/deleted paths,
  dynamic calls and syntax failure; negative fixtures cover corrupted blobs,
  Symlink redirection, namespace drift, producer drift and eviction.
- `.github/scripts/incremental_ccg_benchmark.py` uses the exact Git
  revision of the *real codeQA source repository* and selected file-content
  manifest digests. It measures cold and warm p50/p95, peak allocated memory,
  content reuse and fallback rates at small (5 files), medium (25 files),
  and full-codeQA repository scope. CI publishes a JSON artifact with
  individual scopes and Git/source SHA.

This is a realistic pinned **codeQA repository workload**, not proof of
scalability to an arbitrary multi-million-line monorepo. No speedup is claimed
until there is repeatable comparative data. Should incremental semantic
recomputation ever be considered, it requires a separately verified **upper
bound on every relevant dependency** and differential full-oracle tests.

## Deferred: beyond the safe extraction-cache boundary

- Precise safe subgraph rewrite and build-target compiler dependency tracking;
- Portable cross-platform persistent cache locking beyond POSIX;
- Distributed shared-cache provenance and authenticated storage;
- Real multi-million-line monorepo production benchmark.

These would require a new capability/ADR, not a reinterpretation of this
safety-first cache as a proven complete incremental semantic engine.
