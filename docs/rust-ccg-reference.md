# Pinned Rust → CCG v0.1 reference — sol-adapter-moose

**Status:** hand-curated, source-grounded **conformance fixture** for
[Issue #30](https://github.com/HyungseonSong-plasma/codeQA/issues/30),
a bounded follow-up to [Foundation #1](https://github.com/HyungseonSong-plasma/codeQA/issues/1)
and the [Language Adapter v0.1 protocol](contracts/language-adapter-0.1.md).
This is **NOT a Rust Adapter**. No automated Rust parser, cargo build,
type checker, import resolver or source execution was added.

## Immutable source provenance

Source repository: \`HyungseonSong-plasma/sol-adapter-moose\`  
Exact source commit: \`ce40af4ffda17feaef99f4de328c9a37b6019553\`  
CCG source snapshot identity:
\`git:HyungseonSong-plasma/sol-adapter-moose@ce40af4ffda17feaef99f4de328c9a37b6019553\`.

| Pinned source path | Original Git blob SHA-1 |
| --- | --- |
| \`src/lib.rs\` | \`5c3782e006e693d011f4bc8c4c13b6b028524c35\` |
| \`src/main.rs\` | \`77a65d12abda3e1084a1a206db8b23d096b7b39a\` |
| \`src/ir.rs\` | \`4c7a056d4a6d9aaa0d8c90c6f2bc899edbd515fa\` |

The source bytes are checked in unchanged under
\`fixtures/rust/sol-adapter-moose/src/*.rs.txt\`. The double extension
ensures the source is **inert evidence**, not compiled or collected as
production codeQA Python. The independent
[pinned-source workflow](../.github/workflows/rust-ccg-conformance.yml)
checks out the exact commit from the separate repository and runs \`cmp\`
against each fixture before executing the tests. The local tests also
reconstruct and assert every Git blob ID.

Machine-readable source manifest and exact declaration/use line anchors:
[\`provenance.json\`](../fixtures/rust/sol-adapter-moose/provenance.json).
Hand-curated CCG v0.1 graph:
[\`ccg-v0.1.golden.json\`](../fixtures/rust/sol-adapter-moose/ccg-v0.1.golden.json).

## Manual, deliberately narrow extraction

A human selected **three source files** and a **small subset of directly
observable declarations**. For these selected lines:

- \`pub mod ir;\` at \`src/lib.rs:5\` is a \`module\` declaration, with a
  resolved \`defines\` edge from the **declaring source file**, not a proof
  of the Rust compiler's module loading or type identity.
- \`pub struct FoundationAdapter;\` (\`lib.rs:26\`),
  \`pub struct MooseInputModel\` (\`ir.rs:5\`), \`GeneratedLineMesh\`
  (\`ir.rs:16\`) and \`pub enum VariableOrder\` (\`ir.rs:30\`) are represented
  as generic CCG **\`symbol\`** nodes: the frozen v0.1 graph has no
  Rust-specific \`struct\` or \`enum\` kinds. This is a lossy, documented
  language-neutral representation, **not** a claim that these are classes.
- Observed functions \`main\` (\`main.rs:14\`), \`run\` (\`main.rs:21\`)
  and \`operator_name\` (\`ir.rs:280\`) use the generic CCG \`function\`
  kind. \`FoundationAdapter::describe_adapter\` (\`lib.rs:29\`) and
  \`MooseInputModel::validate\` (\`ir.rs:79\`) use CCG \`method\`.
  The manually read Rust \`impl\` blocks support these parent \`defines\`
  witnesses; no method dispatch is inferred.
- \`use crate::execution_v02::{MOOSE_TARGET, THERMAL_CAPABILITY_V02}\`
  at \`lib.rs:8\`, \`use sol_adaptor_moose::FoundationAdapter\`
  at \`main.rs:10\`, \`use std::process\` at \`main.rs:12\`, and
  \`use std::collections::BTreeSet\` at \`ir.rs:1\` are anchored source
  observations. **Every \`imports\` edge is \`unresolved\`** with its
  spelling retained as \`target_hint\`, never an invented external target.

The location span marks the observed **declaration/use statement line**;
it does not claim to span a whole Rust function body. Node IDs are stable
for this pinned fixture only, not a production Rust symbol identity scheme.

## Source selection and coverage semantics

The Golden graph records \`coverage.status=complete\` for **its three
explicitly supplied source paths**, because those selected inputs have
manually inspected source evidence. It does **not** assert that every
declaration in those files, every Rust crate source file, every import,
or the complete language semantics was extracted. The graph is explicitly
a **selective golden sample**, not whole-repository analysis.

An adversarial control extends the selected set with
\`src/backend.rs\` as an unprocessed path and must report
\`coverage.status=partial\`; a contradictory \`complete\` must fail.
An unprocessed file cannot supply a location-backed graph fact.
This distinction and the curator's limited source selection must be
preserved by downstream consumers.

## Conformance, negative controls and boundaries

[\`tests/test_rust_ccg_reference.py\`](../tests/test_rust_ccg_reference.py)
uses the same \`ResourceRegistry(...).load_json("ccg_schema")\`,
\`codeqa.core.parse_graph\` and \`canonical_json\` as the
[existing Python CCG conformance](../tests/test_python_adapter.py).
It compares pinned source lines to each hand-curated node/edge, verifies
all \`defines\` parent/target witnesses and unresolved \`use\` hints, and
checks canonical serialization regardless of input array order.

Adversarial controls cover unknown imports without invented resolved
targets, missing resolved target/source IDs, duplicate node identity,
uncovered facts and contradictory partial-file coverage.
No new JSON Schema, Rust AST dependency or CCG extension is introduced.

**Quality and runtime boundaries:** a CCG graph of grounded syntax is
not a P1–P8 result, confirmed runtime coupling, ownership decision or
end-to-end adapter verification. \`complete\` file-selection coverage is
not full scientific, semantic or Rust parser coverage. A real Rust Adapter
would require a separate parser/protocol implementation, parser version
and full positive/adversarial conformance suite under
[Language Adapter v0.1](contracts/language-adapter-0.1.md).
