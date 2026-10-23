# Caller-owned mixed-language source selection and coverage v0.1 (#41)

**Contract:** `contracts/adapters/source-selection-v0.1.schema.json`,
registered as `source_selection_schema`. The pure
`codeqa.pipeline.source_coverage.aggregate_source_coverage` reconciles
selected paths against separately supplied CCG graphs and declared
[Adapter v0.1](contracts/language-adapter-0.1.md) capabilities.

## Explicit authority and anti-overclaim controls

Samuel/`chatgpt-operation` acquires repository content and decides which
files were included or excluded. This module makes **no GitHub, filesystem,
parser, cargo or MOOSE calls**. Manifest data is a caller declaration,
not an independent proof that the inventory contains the entire repository.

A v0.1 manifest declares one immutable Git repository identity
(`repository`, full `commit_sha`), discovery method,
`inventory_complete` **caller attestation**, and exact relative POSIX
source paths with `language`, `category` and `selection`. Exclusions must
include a concrete `exclusion_reason`. Vendor and generated source must
have explicit categories; all stated paths and exclusions are retained.
Duplicate or escaping paths are rejected. A manifest never joins two
different repository commits into a fictional single immutable snapshot.

Language adapter capabilities are separately validated through
`adapter_capability_schema` and must declare compatible extensions,
syntax-only execution and CCG v0.1 output. An analyzed graph must match
**exactly the same** snapshot ID and must not contain unselected,
excluded or other-language paths. Unknown source/language pairs are not
silently discarded.

Per-file outcome semantics:

| Status | Meaning |
| --- | --- |
| `analyzed` | Explicitly selected path was reported as parsed by a supported, supplied language adapter graph. This is **not** complete semantic extraction. |
| `unprocessed` | Supported selected path had a parse/coverage error, or adapter was not run; the reason is explicit. |
| `unsupported` | No declared compatible language adapter/extractor; **not** PASS. |
| `excluded` | Caller explicitly excluded file with a stated reason; not certified evaluated. |

`selected_status=complete` means all **included** paths reported analyzed.
It does not mean every file in the repository was selected or all semantic
relationships found. `inventory_confidence=caller_attested` is a label
for a *caller declaration*, never independent snapshot authentication.
A partial Python result with unsupported C++ cannot become a whole-repository
PASS regardless of the Python Mechanical status. Every report carries
`SELECTED_FILES_ONLY_NOT_A_REPOSITORY_QUALITY_VERDICT`.

## Exact pinned reference cases

- **Mixed Python/C++**: `moose-test-repo` at
  `1977ad5559e5aa7a1c8d04c83735c15e007130d5`.
  Byte-identical Python guard
  `ci/guards/physics_dependency_guard.py` (Git blob
  `dc36f7c8a43a5563e86021289f95e6b1de3147d8`) and C++
  `physics_app/src/base/PhysicsApp.C` (Git blob
  `412a4d0b2faf8c228732f5ff64e26f6909340ac3`)
  live under `fixtures/mixed/python/` and `fixtures/mixed/cpp/`
  with inert `.txt` suffixes. The caller manifest
  `fixtures/mixed/moose-selection-v0.1.json` explicitly selects both
  and excludes `README.md` with a reason. Python reports
  `analyzed`; C++ remains `unsupported` because **no C++ Adapter** is
  declared; overall selected coverage is `partial`.
- **Pinned Rust**: `sol-adapter-moose` at
  `ce40af4ffda17feaef99f4de328c9a37b6019553`,
  verified by [Rust CCG reference](rust-ccg-reference.md). Its golden CCG
  is **manually curated**; it is NOT a Rust Adapter and may not be
  submitted as an automated language graph without a real declared
  compatible parser. The source selection contract reports these Rust
  paths as `unsupported` when no Rust analyzer is supplied.
- **Pinned Samuel Python**: the existing
  [Samuel conformance](samuel-adapter-conformance.md) verifies actual
  Python adapter syntax facts at exact source revision
  `9b335e3fbb9c5e8e323e382daeec56fa25336822`.
  That *different repository snapshot* must remain independently scoped,
  not mixed with either the MOOSE or Rust commit.

## Conformance and external-byte verification

`tests/test_mixed_source_coverage.py` tests manifest/schema validation,
exact file SHA, valid Python parse, unsupported C++, excluded documentation,
snapshot mismatch, duplicate/unsafe paths, falsified inclusion/exclusion,
absent adapters, hand-curated Rust exclusion, missing graph paths,
deterministic serialization and caller attestation limitations.

`.github/workflows/mixed-source-conformance.yml` checks out immutable
MOOSE source bytes at the pinned SHA and verifies each copy with `cmp`
before Python conformance tests run. This is independent of the stored
fixture's Git blob comparison.

**Non-goals:** No Rust/C++/Fortran production parser, no cargo build or
automatic source discovery, no modification of CCG v0.1 or QA Result v0.1,
no implicit claim of test relevance, run-time behavior or P1–P8 completion.
