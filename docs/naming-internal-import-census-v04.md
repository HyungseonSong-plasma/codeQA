# #144 Stage 5 — full pinned internal Python import census for one symbol

**Current active scope:** Internal repository source evidence only. External
callers are unavailable and deliberately [deferred to #147](https://github.com/HyungseonSong-plasma/codeQA/issues/147).
No external caller, public SDK, DTO/DB compatibility, or Naming semantic
policy PASS is fabricated.

## Deterministic selection, with explicit denominator

Pinned historical source commit:
`codeQA@1b6dd3329a3c6e4fc70602cdaaea9e2fd0698f76`.
Root Git tree SHA:
`c8a8dd5906d33bf49f46c8a2355f2512c225048b`.

The [versioned corpus charter](../fixtures/naming-governance/codeqa-internal-graph-charter-v04.json)
specifies **exactly 100 Git-tracked Python files** selected by
`src/codeqa/**/*.py` in the pinned tree. The
`naming_internal_import_census_v04` pipeline independently re-enumerates
that immutable tree (not the working tree), reads each selected historical
file with `GitReader`, recomputes its Git blob ID and SHA-256, and AST
parses every file. A missing path, invalid pin, unexpected denominator,
invalid source or existing source-control witness drift cannot yield PASS.

## Strictly bounded binding/provenance rules

The root declaration is the source AST `ControlFlowObservation` class
from `codeqa.core.complexity`, with `node_id: str` limited to a static
stdlib dataclass `FIELD_CANDIDATE`. This is **not** a complete
`node_id` field-usage graph.

All selected internal module sources are inspected for
`Import`/`ImportFrom` syntax, absolute/relative module spellings,
an exact imported root symbol, alias/binding changes, reexport-like
chains, nested imports, wildcard imports, conditional/global namespace
mutations, and dynamic import/binding warning signs. The graph is **root
symbol specific**; it is not a repository-wide binding graph covering
all names. Static transitive chains propagate only through simple,
unambiguous, top-level, exact-name import statements. Cycles lacking a
known origin, aliases, conditional scopes and marked dynamic mutations
remain `UNKNOWN`. Only source-syntax candidates are emitted;
runtime import execution/identity and actual public exports are not
established.

The previous two actual direct class-symbol imports remain mandatory
regression controls:
`adapters/python_complexity.py:12` and
`evaluation/complexity.py:8`. Any additional import/reexport syntax
identified in the pinned 100-file corpus is reported separately, not
automatically promoted to semantic ground truth.

## Scope admission versus actual policy authority

A `DIRECT_OR_CHAINED_IMPORT_SYNTAX_CANDIDATE` edge is a reproducible
AST provenance *candidate*, not a verified runtime reexport, safe rename,
or proof that any client uses `ControlFlowObservation.node_id`.
`graph_completeness=NOT_EVALUATED`,
`runtime_symbol_identity=NOT_EVALUATED`,
`dynamic_import_resolution=NOT_EVALUATED`,
`semantic_fp_fn=NOT_EVALUATED`, and
`glossary_policy=NOT_ADOPTED` remain mandatory. Real role ownership
and path approval have **not** been given; existing `scopes=[]`
and frozen Naming v0.1 remain unchanged.

**External caller evidence:** `DEFERRED_NO_EVIDENCE`, tracked in
[Issue #147](https://github.com/HyungseonSong-plasma/codeQA/issues/147).
It must not gate the bounded internal AST work, and must never be
represented as successful compatibility verification.

Regression:
`python -m unittest discover -s tests -p 'test_naming_internal_import_census_v04.py' -v`

Future internal #144 work may widen symbol coverage, improve binding
resolution with real-source positive/negative witnesses, and establish
a separately versioned domain-semantic owner authority. External
compatibility work resumes only when actual permitted client sources
become available.

## Stage 7 — fail-closed competing symbol bindings

A direct import line does **not** establish a uniquely bound module-level
symbol if the same name is imported again, assigned, deleted, bound in a
top-level loop or conditional statement, or targeted by a walrus expression
or possible nested `global` mutation. The static graph now excludes those
modules with `AMBIGUOUS_TARGET_MODULE_BINDING` or
`UNSUPPORTED_TARGET_MODULE_BINDING`. Repeated imports of the same symbol
from the same source are also ambiguous: the graph does not infer that the
second import is harmless.

A local-only assignment inside a function without `global` is not a
module-level overwrite. The distinction is covered by adversarial tests.
The 100-file pinned source denominator and historic import witness lines
remain unchanged; any count drift is treated as a regression. Even a
conflict-free source chain remains a **syntax candidate**, not runtime
binding identity, Naming semantic approval, or rename safety.

The external-client requirements remain archived in **closed, not-planned
Issue #147**. No external compatibility PASS or reopening is implied.
