# #93 — Pinned C++ tree-sitter source syntax evidence (v0.1)

This is an **optional, read-only C++ syntax extractor**, not a compiler,
framework ABI, override-dispatch or MOOSE input-DSL validator. It extends
the existing manual/synthetic C++ compiler fixture matrix and the separately
pinned Rust tree-sitter adapter without modifying frozen CCG, Naming or
public QA Result contracts.

The parser records exact caller-selected `owner/repo@40-hex-SHA`, source
path and SHA-256, and requires `tree-sitter==0.25.2` and
`tree-sitter-cpp==0.23.4`. The source bytes are parsed without executing
macros, including headers, resolving symbols or building a binary.
The emitted `CppSyntaxEvidence` has deterministic declaration name/line/
container observations, producer versions, parse status and explicit
unknowns. It rejects forged hashes, paths/revisions and parser version drift.

The independently checked **real source sample** is
`HyungseonSong-plasma/moose-test-repo@1977ad5559e5aa7a1c8d04c83735c15e007130d5`
`physics_app/src/base/PhysicsApp.C`, byte-compared against the existing
`fixtures/mixed/cpp/PhysicsApp.C.txt` before the parser is invoked.
The checkout is a pinned *application source sample*, **not** an attested
upstream MOOSE framework release or authoritative DSL grammar. The
existing controlled `fixtures/cpp-override` positive/negative specimens
remain distinct; a syntactically valid `override` is not evidence that
a C++ compiler accepts its base signature. A strict syntax error raises;
an explicitly requested partial parse has
`PARTIAL_SYNTAX_ERRORS_NOT_EVALUATED`, never a PASS.

The `mixed-source-conformance.yml` workflow installs the optional parser,
runs all C++ parser tests with **zero skips**, and uploads a source-bound
`cpp-parser-evidence.json` receipt. Existing mixed-language source
selection checks continue unchanged. The GitHub Actions runner OS and
parser packages are pinned as specified, but package supply-chain
transitive hashes and compiler/framework ABI are not independently attested.

**Unresolved acceptance:** independently pinned C++ compiler toolchain,
full translation-unit/build flags, templates/macros/generated headers,
virtual dispatch and public ABI consumers; actual upstream MOOSE SDK
release, input DSL grammar and reserved-vs-customizable key adjudication;
Rust trait/compiler evidence and human Naming approval. All remain
`NOT_EVALUATED` pending separate evidence. No source/DSL migration,
rename or production authorization is issued.
