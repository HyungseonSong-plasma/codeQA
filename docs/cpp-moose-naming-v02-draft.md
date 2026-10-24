# C++ override and MOOSE DSL evidence v0.2 draft (#73)

Status: **partial, opt-in, compiler-fixture evidence only**. This is not a
production C++ parser, a pinned MOOSE SDK build, or a MOOSE input-language
grammar certification.

The eight C++ specimens in `fixtures/cpp-override/` distinguish valid
overrides, covariant returns, missing base members, same-name overloads,
nonvirtual members, `noexcept`, `const` and return-type mismatches. When
a C++ compiler is available, the conformance test invokes `-std=c++17
-fsyntax-only -Werror` and checks expected successful/failed compilation,
without executing binaries. The test reads each toolchain's `--version`
during validation; the CI runner/toolchain identity must still be pinned
before claiming independent compiler provenance. An absent compiler causes
a declared skipped test, **not** a verified result.

MOOSE input DSL identifiers have a separate namespace.
`profiles/cpp-moose-naming-v0.2-draft.json` declares `Kernels` as a
case-sensitive application-provided reserved specimen. The conservative
`classify_moose_identifier` returns `PRESERVE_DECLARED_RESERVED_KEY` for
that exact declared key and `NOT_EVALUATED` for `kernels` or any
unverified framework key. It does **not** claim an official MOOSE grammar,
framework release, macro expansion, dynamic ABI safety, or parse coverage.

## Full acceptance still requires

- parser-backed C++ source locations and category coverage;
- pinned real MOOSE framework and DSL grammar/parameter/keyword contracts;
- positive/negative real framework specimens and versioned source selection;
- public SDK/ABI and dynamic linkage consumer review;
- project-selectable conventions and documented unsupported templates/macros;
- a separately approved plan for any eventual migration.

No source or input file is renamed; frozen Python/CCG/Naming/Mechanical/QA
Result/Delta contracts are unchanged.
