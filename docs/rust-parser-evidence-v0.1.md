# Rust parser-backed source witnesses v0.1 (#93)

This is a **new, optional, read-only** parser-backed syntax evidence path,
separate from the existing manual Rust Naming v0.2 draft and frozen CCG v0.1.
It does not claim that #93's final Rust production mode has been approved.

## Actual pinned producer and source

The dedicated `Pinned Rust Parser Source Evidence` workflow installs
`tree-sitter==0.25.2` and `tree-sitter-rust==0.24.0` (exact Python
distribution versions), then independently checks out
`HyungseonSong-plasma/sol-adapter-moose` at
`ce40af4ffda17feaef99f4de328c9a37b6019553`. It compares the exact
`src/lib.rs`, `src/main.rs` and `src/ir.rs` bytes against codeQA's
already-pinned fixture before producing a path/line/digest-bound AST witness.

The parser records trait, struct, enum, module, function and method spelling
from tree-sitter nodes, retaining raw identifier spelling. Source parse errors,
unreviewed parser versions, stale digests and unpinned revisions fail closed.
Unknowns explicitly cover trait impl resolution, macros, reexports, attributes,
compiler/ABI and runtime dispatch. The workflow asserts seven tests actually
execute without skip and uploads `rust-parser-evidence.json`.

## Authority and limitations

`RustSyntaxEvidence.authority` is always
`PARSER_SYNTAX_ONLY_NOT_COMPILER_OR_TRAIT_PROOF`. Syntax agreement does not
verify that an `impl Trait for Type` satisfies an external trait contract,
resolve reexports, expand procedural macros, establish lifetimes or prove
public ABI compatibility. Exact parser package versions are pinned; Python
wheel hashes and parser native binary supply-chain attestation are still
`NOT_EVALUATED`. The external repository SHA and fixture comparison are
verified by CI, not by callers of the pure parsing function.

C++ parser/ABI, real MOOSE framework release and input DSL grammar, Rust
compiler/type checking against pinned external crates, human naming
adjudication and compatibility decisions remain open #93 acceptance items.
No automatic rename, SDK mutation or production source execution occurs.
