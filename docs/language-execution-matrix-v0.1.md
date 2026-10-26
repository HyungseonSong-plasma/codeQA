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

## #93 parser-backed Rust source witness (integration only)

The combined #93 parser producer is `codeqa.adapters.rust_parser_evidence:parse_rust_syntax`, exercised by `.github/workflows/rust-parser-evidence.yml` against immutable Rust source. The Rust parser cell remains `PARTIAL_FIXTURE`; successful tree-sitter syntax parsing does **not** establish trait resolution, macro expansion, public ABI, compiler compatibility or a full Rust Mechanical pipeline. The independent #122 and #93 PRs must be reviewed/merged in dependency-safe order before this combined matrix becomes the main-branch source of truth.

## #93 parser-backed C++/MOOSE source witness (integration only)

The combined C++ producer `codeqa.adapters.cpp_parser_evidence:parse_cpp_syntax`
runs with pinned optional tree-sitter C++ syntax grammar in the existing
`mixed-source-conformance.yml` workflow. It parses the byte-checked
`moose-test-repo@1977ad5559e5aa7a1c8d04c83735c15e007130d5`
`PhysicsApp.C` application specimen and controlled positive/negative C++
override fixtures. The cell is **PARTIAL_FIXTURE**, not `SUPPORTED_SCOPED`:
missing framework headers, macro expansion, virtual dispatch, ABI, upstream
MOOSE framework release and input-DSL grammar remain `NOT_EVALUATED`.
A syntactically valid but compiler-invalid `override` is explicitly not
promoted to compiler evidence. The source/entrypoint/workflow and bounded
limitation are guarded by negative tests on the combined tree. This is
not an independently approved C++/MOOSE production parser pipeline.
