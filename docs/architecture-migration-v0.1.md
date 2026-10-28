# Architecture QA B5 — migration and public-import impact evidence v0.1

**Status:** source-bounded, read-only advisory. **Issue:** #171. **Prerequisites:** merged B1 #167, B3 #169, B4 #170. No automatic import rewrite, file move, ABI claim or semantic proof.

## Contract and provenance

`codeqa.evaluation.architecture.migration.assess_architecture_migration(inventory, scenarios, source_texts)` consumes the B1 inventory, B4 virtual candidates and caller-attested source bytes from the **same exact Git commit**. It checks B1/B4 report digests, snapshot/policy/inventory identity, per-moved-path source hashes, and the hashes of all supplied source bytes. The Git-based CI audit independently verifies each available blob against B1 before calling the pure estimator. The B4 self-digest is **not independent B2/B3 provenance**; the audit first generates the B1→B2→B3→B4 chain from the exact checked-out HEAD.

The estimator never creates an architecture question. It only inspects actual B4 candidates and returns an empty candidate list for a healthy/no-question baseline. Naming extraction, sibling adapters, and language-family grouping are regression topics, not built-in targets. A candidate that requires a new top-level package or distribution is beyond B4's frozen-scope mapping contract; it is not silently synthesized or marked safe.

## Observable evidence and conservative interpretation

For each B4 candidate, the report includes moved source paths, old/proposed dotted module identities, source-hash- and line-bound observed import/reference sites, affected file/site counts, `__init__` re-export paths, and explicit unresolved risk flags. The static scan distinguishes ordinary/aliased imports, from-imports, relative imports, star imports, dynamic import literals and unknown dynamic targets. It also searches tracked tests, scripts, configuration, documentation and packaging metadata for path references. Source parsing gaps and omitted readable files are reported; absent observed callers do **not** prove absent external consumers.

A free destination filesystem path can still conflict with an existing Python dotted package namespace (e.g. `new.py` versus `new/__init__.py`). This is `BLOCKED`, not an automatic rewrite. Other sites are always `REVIEW_REQUIRED`; import aliasing, star exports, relative resolution, `__all__`, entrypoints and package/resource registration need explicit compatibility work and tests.

Cost bands are transparent **work-surface proxies**, not engineering-hour forecasts: `BLOCKED` for dotted namespace collision; `HIGH` for >10 observed sites or star/CLI/cross-distribution risk; `MEDIUM` for >2 sites, multiple moves, or dynamic/metadata/export/relative risks; `LOW` otherwise. Even `LOW` retains unknown external consumers and runtime semantics. All unblocked compatibility verdicts remain `NOT_EVALUATED`, and the overall B5 evidence status remains `INCOMPLETE`.

Forwarding modules, facades, deprecation windows and separate distributions are **non-automatic options** requiring their own contract, versioning, packaging, import and consumer validation. No compatibility pattern is applied by this analyzer.

## Verification and limits

`tests/test_architecture_migration_v01.py` includes arbitrary/renamed package fixtures, no-question baseline, static/aliased/relative/re-export/dynamic/CLI/metadata witnesses, missing-source and syntax-gap controls, dotted namespace collision and tampered identity/hash rejection. `.github/scripts/architecture_migration_audit.py` validates the JSON Schema and produces an exact-head B5 artifact. B7 #173 must treat static proxies and compatibility unknowns as decision gates, never turn a path-only improvement into a certified `PREFER`.

**Known gaps:** full Python import semantics, runtime import hooks, external consumer census, ABI, namespace-package semantics, transitive packaging dependencies, non-Python callers and actual post-migration parity. These remain `NOT_EVALUATED` pending independent evidence and a separately approved migration PR.
