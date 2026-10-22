# Python Adapter v0.1

`codeqa.adapters.adapt_python_sources(sources, snapshot_id=..., schema=...)`
is a syntax-only CCG extractor. Source inputs are an explicit in-memory map of
snapshot-relative POSIX paths to Python source strings. The external caller
supplies the pinned source snapshot and the CCG JSON Schema (via the logical
`ccg_schema` resource ID); the adapter does **not** read arbitrary filesystem
trees, run source code, invoke Git, or mutate GitHub.

It emits:
- File, class, function and method nodes; resolved `defines` edges.
- Observed `imports` and `inherits` stay `unresolved`; most dynamic calls
  stay `unresolved` with an observed `target_hint`.
- Direct calls from a module-level function to a **unique, undecorated,
  unshadowed function in the same module** may be linked to the corresponding
  CCG Node as `resolved`, with provenance `lexical_module_binding`.
  This is static lexical evidence, **not a guarantee of runtime dispatch**.
- Module/import rebinding, duplicate definitions, wildcard imports, local
  variable or argument shadowing, conditional definitions, methods, nested
  scopes, cross-file imports and attribute calls are conservatively excluded
  from this resolution.
- Locations and `python-ast` provenance, explicit parse coverage and
  syntax diagnostics. Unsupported extensions remain unprocessed.
- Stable IDs derived from path, qualified lexical name, line and column.
  Changing the location can change the ID; this is expected for v0.1.

**Limits:** `complete` means all supplied `.py` files parsed successfully,
*not* full semantic completeness. Decorator and function signature expression
calls, lambda bodies and dynamic dispatch are not comprehensively modeled.
This adapter does not infer runtime identity when monkeypatching, `exec`
or reflective attribute operations change bindings.
Unknown import/call targets are not invented, and deeper language adapters will
require separate capability contracts. Use the immutable snapshot ID supplied by
the caller; no snapshot acquisition occurs here.

## Import dependency companion view

The Python pipeline additionally exposes a static import-to-source-file
correspondence model and a reverse-impact query. See
[Dependency and Impact v0.1](dependency-impact.md). A module-path match
is **not** the same as CCG `resolved` runtime symbol identity, so existing
CCG `imports` edges remain unresolved.
