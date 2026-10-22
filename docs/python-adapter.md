# Python Adapter v0.1

`codeqa.adapters.adapt_python_sources(sources, snapshot_id=..., schema=...)`
is a syntax-only CCG extractor. Source inputs are an explicit in-memory map of
snapshot-relative POSIX paths to Python source strings. The external caller
supplies the pinned source snapshot and the CCG JSON Schema (via the logical
`ccg_schema` resource ID); the adapter does **not** read arbitrary filesystem
trees, run source code, invoke Git, or mutate GitHub.

It emits:
- File, class, function and method nodes; resolved `defines` edges.
- Observed `imports`, `inherits` and `calls` edges marked `unresolved`,
  with source expression as `target_hint`. No guessed cross-file bindings.
- Locations and `python-ast` provenance, explicit parse coverage and
  syntax diagnostics. Unsupported extensions remain unprocessed.
- Stable IDs derived from path, qualified lexical name, line and column.
  Changing the location can change the ID; this is expected for v0.1.

**Limits:** `complete` means all supplied `.py` files parsed successfully,
*not* full semantic completeness. Decorator and function signature expression
calls, lambdas and dynamic dispatch are not comprehensively modeled.
Unknown import/call targets are not invented, and deeper language adapters will
require separate capability contracts. Use the immutable snapshot ID supplied by
the caller; no snapshot acquisition occurs here.
