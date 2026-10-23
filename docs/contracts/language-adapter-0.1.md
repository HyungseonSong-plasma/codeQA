# Language Adapter capability/conformance protocol v0.1

**Status:** Versioned public capability **declaration** and conformance contract.
**Owner:** codeQA adapters boundary; parent #1; tracked in #29.
**Authoritative schema:** `contracts/adapters/capability-v0.1.schema.json`
(logical `adapter_capability_schema`). The runtime CCG v0.1 schema remains
`contracts/ccg/graph-v0.1.schema.json` and is unchanged.

## Ownership and input identity

The orchestrator/caller selects an immutable repository snapshot; acquisition,
GitHub credentials and mutation remain Samuel/`chatgpt-operation` responsibilities.
Adapters consume caller-provided inputs and declared configuration. The CCG Core
neither imports language parsers nor infers repository policy. Analysis profiles,
evaluation rules and quality verdicts are separate from CCG facts and this manifest.

Each manifest must declare adapter ID/version/language, parser name and version,
execution safety, accepted source representation and extensions, caller vs
adapter snapshot identity/acquisition, inclusion/exclusion configuration, output
graph version/kinds, fact resolution states and extraction features.

The current `python_adapter_capability` profile faithfully specifies **only**
the implemented in-memory path→source API, explicit caller-owned `snapshot_id`,
Python standard-library AST, `.py` input and limited optional caller-owned
caching. There is **no built-in glob include/exclude selection** and no claim
of a configurable Python parser feature version.

## Conformance and uncertainty

1. Verify the manifest against JSON Schema Draft 2020-12 **and** semantic
   checks for duplicate feature names and contradictory configuration.
2. Verify that emitted JSON conforms to CCG v0.1 and to the **declared** node/
   edge kinds. Core semantic validation rejects malformed paths, missing
   targets, cyclic containment and conflicting coverage.
3. Record actual file-level `complete`, `partial` or `none` parse coverage,
   analyzed files and unprocessed reasons. `complete` is scoped to the
   **supplied input only**, not all source files that could exist in a repo.
4. Use feature statuses `SUPPORTED`, `PARTIAL` and `NOT_EVALUATED`. A
   `PARTIAL` feature needs a concrete bounded evidence scope. An unimplemented
   analyzer or unsupported syntax is `NOT_EVALUATED`, never PASS.
5. All resolved CCG edges must have a witnessed target; uncertain imports and
   dynamic calls preserve syntax-grounded `target_hint` with
   `resolution=unresolved`. Module-path or cross-module declaration
   **candidates** are not exact runtime dispatch identity.
6. Same pinned source, explicit parser/profile versions and configuration must
   yield byte-stable `canonical_json(graph)` for the same toolchain. Source
   relocation may change the line-derived symbol ID.
7. Validation/CI success establishes only **contract conformance**, not
   quality, runtime or domain correctness. Semantic claims need separate
   context and evidence, not names or surface syntax.

Negative controls must include: invalid/duplicate feature identifiers, absent
parser identity, unsupported version, contradictory configuration, missing
coverage, unresolved call with invented target, syntax errors, decorator/
signature/lambda gaps and shadowed/ambiguous bindings.

## Python v0.1 supported and unsupported examples

**Supported syntax extraction:** file/class/function/method definitions,
nested/async definitions, source line intervals, `import` / `from`
including aliases/relative syntax, conditional/star import syntax observation,
explicit parse diagnostics. `defines` are grounded and resolved. `imports`
are syntax-grounded but unresolved. Same-module direct lexical calls are
resolved only when unique, undecorated and unshadowed.

**Partial/not evaluated:** decorators and signature expression calls,
lambda body calls, arbitrary dynamic/method dispatch, cross-file exact calls,
built-in include/exclude globbing and parser feature-level configuration.
Conditional/star import *semantics* remain unproven; observing the syntax
never establishes an executable binding.

See `docs/python-adapter.md` and #24 for the separately pinned Samuel
source fixture and positive/adversarial Python integration checks. A future
Rust adapter reuses this contract without importing Python AST types.

## Compatibility discipline

Published profile/schema IDs are immutable for this version. Schema changes
require explicit versioning and migration tests; never silently extend CCG
v0.1 or describe internal Python reports as universal QA Result v0.1 (that
distinct contract is tracked by #28).
