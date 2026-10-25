# Per-language executable capability matrix v0.1 (#122)

The [checked machine-readable matrix](../profiles/language-execution-matrix-v0.1.json)
separates **parser**, **CCG**, **Mechanical P1/P3**, **Naming**, **Formal Gate**
and **production ABI** for Python, Rust, C++/MOOSE and Dafny-generated Python.
Every cell carries an explicit limitation; no cell claims universal P1–P8 PASS.

- `SUPPORTED_SCOPED`: only implemented Python syntax/CCG/Mechanical P1/P3
  entrypoints with existing source and workflow witnesses. An existing CI
  workflow file is not evidence that it passed at the present commit; live
  exact-head runs must be inspected independently.
- `PARTIAL_FIXTURE`: pinned source or manually scoped fixture, not a runnable
  production language pipeline. Rust golden CCG and MOOSE P3 review fall here.
- `FIXTURE_ONLY`: controlled generated-Python Dafny Gate, never production
  merge or semantic preservation approval.
- `NOT_EVALUATED`: no supported pipeline/ABI claim; does not mean a defect
  was proven.

The validator checks the actual source and top-level entrypoint symbols,
workflow file witnesses and prohibited promotions. The source of truth for
Python AST extraction remains the existing `python_adapter_capability`
resource and v0.1 CCG contract; neither is modified by this inventory.

## Contributor template for a new adapter

Before upgrading a language/layer cell: independently pin source acquisition
and parser binary/configuration; declare a versioned adapter capability
manifest and selection scope; implement a syntax-only CCG converter without
putting language ASTs in Core; execute exact-source golden and adversarial
conformance against CCG v0.1; implement rule-specific Mechanical semantics
with separate analysis limitations; and obtain independently reviewed external
ABI/SDK witnesses for any production claim. Add a real callable entrypoint and
matching exact-head CI. This checklist is a proposal, not an exercised new
non-Python adapter. New-adapter end-to-end onboarding is `NOT_EVALUATED`.

See #93 for missing production Rust/C++/MOOSE framework ABI/DSL evidence.
