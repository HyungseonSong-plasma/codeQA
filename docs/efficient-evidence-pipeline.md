# Efficient evidence and incremental Python analysis

codeQA composes multiple reports from **one Python AST parse per source file**
within each analysis. Python AST values remain Adapter-private; CCG v0.1
and the language-neutral Core model remain unchanged.

## Implemented work, in priority order

1. Parse once: `adapters/python_snapshot.py` parses each Python file one time,
   sharing the parsed AST with CCG extraction and dependency analysis.
2. Shared evidence: `core/evidence.py` holds immutable evidence records and
   language-neutral cross-report relationships. IDs are deterministic hashes
   of file path, line, column, syntax kind and observed expression.
3. Linked modules/symbols/functions: `adapters/python_evidence.py` links
   observed Import syntax to both CCG unresolved symbol facts and the matched
   module-path evidence; statically proved local function calls use the same
   index. These layers are not conflated: module-path correspondence is **not**
   a resolved symbol or verified runtime dependency. Ambiguous same-line
   syntax without CCG column evidence receives a `null` evidence link.
4. Incremental reuse: an optional caller-owned `PythonAnalysisCache` caches
   parsed AST and file-local CCG facts using `(path, SHA256(source contents))`.
   Snapshot-wide module mappings, CCG semantic validation, evaluator results,
   evidence links and impact indexes are recomputed each run. This is needed
   because adding/deleting another file may alter reference resolution even
   when an importing file does not change. A changed file is re-extracted.
5. Unified report: `PythonAnalysis.summary_document()` gives a short summary
   across coverage, quality, CCG, dependency and evidence limitations,
   efficiency counters and optional impact. Full `to_document()` retains
   separate graph, QA, dependency, evidence and impact detail.

## Usage

```python
from codeqa.adapters import PythonAnalysisCache
from codeqa.pipeline.python import analyze_python

cache = PythonAnalysisCache()
first = analyze_python(sources_before, snapshot_id='sha-before',
    ccg_schema=schema, mechanical_profile=profile, cache=cache)
second = analyze_python(sources_after, snapshot_id='sha-after',
    ccg_schema=schema, mechanical_profile=profile, cache=cache,
    changed_paths=('src/codeqa/core/graph.py',))
print(second.summary_document())
print(second.impact.to_document())
```

Without the optional cache, there is **no cross-request global state**.
`efficiency.parsed_files` and `reused_parses` count Python parse work;
`extracted_files` and `reused_extractions` count CCG local extraction work.
These are deterministic work counters, not measured CPU or memory speedups.

Impact traversal is **lazy**, executed only for `changed_paths`, using one
multi-source traversal. It expresses **STATIC_POTENTIAL_ONLY** Import paths.
Absence from the result does not certify a module/test as unaffected;
dynamic imports and dependency injection may be missed. No P1–P8 full
quality certification or stable public Quality Report Contract is claimed.
