# Python Naming Coverage v0.2 — opt-in additional evidence (#69)

**Status:** limited Phase 2 implementation; **does not close #69**.

This is an *additive* companion to the frozen Naming v0.1 model; it does
not modify the v0.1 profile, AST extractor, report schema or findings.
The source caller must provide the identical `ParsedSnapshot` and
UTF-8 selection to both adapters. The pure evaluator consumes the v0.1
evidence, new v0.2 evidence, and two independently fingerprinted profiles.

Use registered resources `python_naming_coverage_v02_profile` and
`naming_coverage_v02_report_schema`; call
`extract_python_extended_naming(parsed, sources, snapshot_id=...)`
followed by
`evaluate_extended_naming(baseline, extended, sources,
baseline_profile=..., policy=...)`.

## What is actually measured

- A top-level or class annotated `typing.Final` /
  `typing_extensions.Final` declaration is a **constant-name
  intent**. Enforce `UPPER_SNAKE_CASE` on that witnessed name
  **without proving immutability**. Plain uppercase assignments are
  `constant_intent` uncertainty rather than silently typed constants.
- Direct `self.attribute = value` or annotated assignment under a
  simple `__init__(self)` is a **source spelling observation**, not
  proof of actual instance storage. When the class inherits from a
  base, the attribute's contractual status is unresolved. Recursive
  nested/conditional assignments, descriptors and dynamic `setattr`
  are **not** considered verified declaration bindings.
- Nested lexical declarations, decorators, wildcard/relative imports
  and dynamic namespace operations have **explicit uncertainty
  records**, not a fabricated conformance verdict. Unicode
  identifiers requiring NFKC normalization remain `NOT_EVALUATED`.
- Module/class rebinding of imported `Final` names now records explicit\n  `annotation_binding` uncertainty instead of claiming a verified constant.\n- Each observation binds exact original file SHA-256, line and UTF-8
  byte offset. A spoofed or stale position raises an error. The
  evaluator also validates v0.1 source-identity parity before emitting
  supplementary findings.

**Policy precedence:** exact attested exception for one
`path + owner + kind + name` > longest matching path prefix of that
symbol kind > language-default style. Same-precedence conflicting rules
and duplicate exception identities are errors. A declared exception
requires provider, version and rationale; its outcome is
`EXEMPT_BY_DECLARED_CONTRACT`, **not** evidence of an actual external
contract. Vendor/generated exclusions stay explicit. Profile SHA-256
fingerprints make policy changes visible.

**Interpretation:** `REVIEW_REQUIRED` is a lexical candidate;
`CONFORMANT_WITH_APPLIED_RULE` is one syntax rule;
`NOT_EVALUATED` and recorded uncertainty preserve the incomplete
source/semantic coverage. A v0.2 status never certifies all Python
names or runtime behavior. The v0.1 evaluator may still classify
a Final class attribute differently: consumers must **not combine
v0.1 and v0.2 findings into one global count or infer improvement**.
A unified precedence and coverage contract is still under #69.

## Evidence and work remaining

`tests/test_naming_coverage_v02.py` includes typed `Final` and
direct instance assignments, `typing` aliasing, dynamic source,
import/override unknowns, Unicode identifiers, exact exceptions,
path precedence conflicts, incomplete parsing, generated/vendor
exclusions, source/position tampering, and frozen v0.1 behavior.

A real source fixture
`fixtures/naming-codeqa/python_snapshot.py.txt` is independently
byte-checked against
`codeQA@ef6359131f0cd952ed43674274ffe0453c6bf2a9` in CI.
The test of that file demonstrates deterministic **sample evidence**,
not an independently human-reviewed false-positive/false-negative
inventory or whole-repository coverage.

**#69 remains OPEN** pending real maintainer-reviewed source inventory,
more declaration types (including complicated dynamic module bindings,
import re-exports, nested binding semantics, more complex Final binding transformations),
full exception precedence and signed source/consumer schema provenance.
Related #70 and #71 separately own external runtime bindings; #72/#73
own additional languages. No silent changes to public CCG/QA Result/Delta
or v0.1 naming resource identities.
