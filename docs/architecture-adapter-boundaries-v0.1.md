# Architecture QA B6 — generic language-adapter boundary readiness v0.1

**Issue:** #172. **Status:** opt-in, source-backed architecture advisory. No parser implementation, package move, public import rewrite, ABI claim or architecture PASS.

## Inputs and authority

`assess_adapter_boundaries(inventory, metrics, declaration)` consumes B1 inventory and B2 static dependency metrics from the **same exact Git commit** and a separately versioned owner declaration. It verifies B1/B2 report digests, source/policy identities, declared path membership, static import source SHA/line witnesses and denominators. It does not infer target language from filenames or automatically invent `pythonqa`, `rustqa` or `cppqa`.

`profiles/architecture-adapter-boundaries-v0.1.json` records observed Python implementation-file ownership by target language family. This is **not** evidence of end-to-end target-language parsing. Python support remains scoped; Rust/C++/MOOSE parser/compiler provenance, macro/header/trait resolution and runtime semantics remain `NOT_EVALUATED`. Unassigned adapter modules are counted as `unclassified_paths`, never silently assigned by spelling. Shared helpers are explicitly identified.

## Measured evidence and bounded alternatives

For B2-observed Python static import pairs touching the adapter scope, B6 counts `WITHIN_FAMILY`, `CROSS_FAMILY`, `SHARED_UTILITY`, `UNCLASSIFIED` and `EXTERNAL_BOUNDARY`. Cross-family pressure is only a **question signal** when at least two witnessed cross-family directed pairs form at least 20% of observed adapter-internal pairs. The report includes source path, SHA, line and benign counterhypothesis. No hardcoded family names affect scoring.

`KEEP` is always the baseline. `GROUP_BY_DECLARED_LANGUAGE_FAMILY` is considered only when measured pressure exists across at least two declared families. A `SIBLING_DISTRIBUTION` alternative additionally requires independently declared verified packaging and external-consumer evidence. Even then B6 returns `NOT_EVALUATED`; B7 owns comparative dispositions and no automatic migration is permitted. Shared utility use alone, a healthy single-family package, missing parsers, or arbitrary language names do not force a split.

## Missing evidence and negative cases

Dynamic plugin loading, unknown external callers, Python dynamic imports, cross-language import correspondence, shared utility semantic ownership, Rust macros/traits, C++ macro/header semantics, compiler/runtime provenance and distribution/entrypoint compatibility cannot be proven by this static graph. `INCOMPLETE` is not PASS. The current declaration deliberately leaves unsupported language parser and distribution evidence unresolved rather than creating empty packages.

## Verification

Run `python -m unittest discover -s tests -p 'test_architecture_adapter_boundaries_v01.py' -v`. The exact-head CI pipeline generates B1 and B2 artifacts, invokes `.github/scripts/architecture_adapter_boundaries_audit.py`, validates `contracts/qa/architecture-adapter-boundaries-v0.1.schema.json` and uploads `architecture-adapter-boundaries.json`. The evaluator is pure and read-only; existing CCG, QA Result, frozen root and Mechanical verdict contracts remain untouched.

**Next:** B7 #173 must assess KEEP versus justified alternatives using identical source/coverage and migration/API evidence. B8 #174 must demonstrate unprompted discovery and reproducible exact-head reports.
