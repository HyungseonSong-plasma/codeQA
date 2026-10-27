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
compiler/ABI and runtime dispatch.

The parser now requires a syntactically scoped `owner/repo` identifier, a
relative traversal-free `.rs` path, a full 40-hex source revision and exact
SHA-256 bytes; it rejects sources over 1,000,000 bytes before parsing. These
are **input-integrity guards**, not independent verification that the supplied
repository, revision or path actually exists. The dedicated workflow still
performs that external checkout and byte comparison. The workflow asserts seven tests actually
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


## Same-file Rust trait method lexical comparison (bounded D5 evidence)

The optional \`compare_local_trait_method_spellings\` helper accepts a typed,
source-hash-bound tree-sitter syntax receipt and two exact simple identifiers.
It compares method **spellings only** between a locally declared
\`trait Action\` and a literal \`impl Action for Engine\` in the *same selected
source bytes*. The emitted statuses are \`LEXICAL_METHOD_NAME_SET_PRESENT\`,
\`LEXICAL_NAMES_ABSENT_FROM_IMPL\` or \`NOT_EVALUATED\`. A missing method is
a lexical gap, not a compiler-error claim: default trait methods or macros
may change actual satisfaction. Generic/qualified/external trait headers,
unresolved declarations, trait bodies without an impl, and ambiguous data
remain \`NOT_EVALUATED\`.

The result always carries \`authorization=NONE_SOURCE_SYNTAX_ONLY\` and
\`RUST_COMPILER_TRAIT_SATISFACTION_NOT_EVALUATED\`. Even matching literal
spellings do not demonstrate trait identity, method signatures, lifetimes,
crate dependency resolution, macro expansion or ABI compatibility. This
is not production Rust compilation or an approved Naming policy.
CI's independently pinned source checkout remains the authority for actual
external repository/byte identity; the helper itself cannot attest it.
