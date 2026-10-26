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


Python v0.1's `SUPPORTED_SCOPED` parser/CCG/Mechanical cells are now
protected by exact syntax-bound limitation strings. Rewording any such cell
to imply verified dynamic dispatch, runtime call resolution or complete
P1–P8 Mechanical support is rejected until a separately reviewed/versioned
capability update with new source and execution evidence. Two regression
tests cover these negative promotions. This is a source/contract boundary,
not a substitute for real compiler, SDK or installed-consumer conformance.

## Portable evidence path guard

The read-only matrix rejects control-byte, alternate-data-stream colon and
trailing dot/space source/workflow paths before looking up claimed evidence.
A portable path plus a present source file still does not attest executed
matching-SHA CI, real non-Python Mechanical parity, compiler ABI or DSL
compatibility. Those claims remain limited by each cell's explicit status.

## Current Python Naming scope integration — 2026-10-26

This version's source baseline is the then-current `main@ce147bd5348294823664f13ab539aabe6e24d827`. The
Python `naming` row points at the actual explicit opt-in product wrapper
`codeqa.pipeline.naming_product:analyze_python_naming_opt_in`, not a default
Mechanical/P1/P3 entrypoint. The official separately registered Naming v0.5
policy is restricted to `ControlFlowObservation.node_id` at one pinned field;
this row does **not** grant v0.5 across other Python names. The declared
`PARTIAL_FIXTURE` status is intentional. Negative controls prevent expanding
this to `SUPPORTED_SCOPED`, changing the wrapper path, or claiming complete
SDK/runtime semantic conformance. #147 is archived (closed / not planned).

**Execution note:** Source files and workflow paths are checked here. The
manifest itself explicitly cannot attest a successful GitHub workflow run.
Exact PR head and associated actual CI results must be read separately before
merging, and the source baseline remains a historic input snapshot afterward.
