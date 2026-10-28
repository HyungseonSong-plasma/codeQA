# Architecture QA B4 — evidence-triggered virtual scenarios v0.1

**Status:** opt-in, read-only source-derived hypotheses; not a code move, API rewrite, architecture verdict or migration authorization. **Issue:** #170. Requires merged B1 #167, B2 #168 and B3 #169.

## Input and provenance

`codeqa.evaluation.architecture.scenarios.generate_virtual_layout_scenarios(inventory, metrics, opportunities, role_policy)` consumes the same immutable Git commit and policy digest used by B1–B3. B3 opportunities are deterministically recomputed from B1/B2 and checked for exact equality before any candidate is emitted. The original source hashes, static pair identities, B2 dependency profile and role policy remain fixed.

The result always includes **baseline KEEP**. If B3 discovers no question, no candidate is generated. Automatic candidates are triggered only by witnessed `DECLARED_BOUNDARY_CONFLICT` and `CROSS_BOUNDARY_CONCENTRATION` signals. They are one-file role-boundary relocation hypotheses, never name-driven templates. A static cycle alone yields `PATH_MOVE_CANNOT_REMOVE_STATIC_CYCLE` rather than a fake cycle improvement. The original Naming, sibling-adapter and language-family topics are **not** inserted by default.

## Virtual comparison and conservative gates

A candidate maps existing source paths bijectively to valid, unused paths under already-declared roles within the same source scope. The evaluator rejects invalid/absolute/traversal paths, frozen-root escapes, unclassified/unread source, package-initializer moves, collisions, chained/cyclic moves, unchanged mappings and new declared forbidden dependency directions. Every rejection includes the B3 opportunity ID and a concrete reason.

The evaluator preserves all observed import edges and source bytes. It recomputes declared-role cross/within directed-pair **proxies** under virtual path ownership, and records the delta. **A lower cross-role pair count caused only by path relabeling is not evidence of reduced physical coupling, improved cohesion or safe migration.** Static resolved-pair count and cycle count deltas remain exactly zero. For every edge touching a moved file, the report emits a source-line/hash-bound **rewrite candidate**, explicitly `NOT_EVALUATED`; no import statement is changed.

Known forbidden direction introduced by the candidate is a hard rejection. Other risks remain unresolved: relative imports, public module paths, entrypoints, packaging, downstream callers, semantic responsibility and runtime behavior. These are explicit unknowns. Candidate and overall decisions are always `NOT_EVALUATED`. B5 #171 must investigate migration/public API compatibility; B7 #173 may compare validated candidates but must not treat a proxy-only improvement as `PREFER`.

The separate `candidate_mappings` parameter permits an explicit source-triggered comparison, keyed by **real B3 opportunity IDs**. It does not inject arbitrary new questions into default discovery.

## Exact collision provenance (follow-up #184)

When a proposed mapping collides with an existing source path or another
proposed destination, B4 rejects it with `TARGET_COLLISION` and emits
`collision_witnesses`. Each witness binds the actual source path and
proposed target path to the source SHA-256. An occupied target additionally
records its own SHA-256; duplicate destinations record the other competing
source paths. These are deterministic, read-only path-identity facts, **not**
evidence that renaming to a different path would be safe or beneficial.

B8 carries these rejection witnesses into its human report. The default
automatic mapping still selects the same candidate and does not silently
invent an alternative destination. Static ownership intent, external imports,
public API compatibility and safe cleanup remain `NOT_EVALUATED`.

## Verification

`tests/test_architecture_scenarios_v01.py` covers healthy zero-scenario, favorable and unfavorable *role proxy* deltas, no-op/collision/invalid/root/chain rejection, new forbidden direction, cycle non-solution, renamed-isomorphic fixtures, report tampering, schema validation, immutability and exact-head real codeQA self-diagnostic. The CI audit reuses B1→B2→B3 exact-head artifacts and validates B4's versioned JSON Schema. No production package location or public import is changed.

## Known limits and next gate

Static imports are incomplete for dynamic/conditional/runtime imports; external consumers, co-change, cross-language imports and semantic cohesion remain unverified. Package moves with new package initializers, distribution split or module import rewrites are **not performed**. If evidence cannot support a candidate, zero candidates or a rejection is a valid result, not a PASS.

**Next:** B5 migration estimator and B7 bounded counterfactual decision. Real refactoring requires a separately approved PR, exact-head CI and post-change evidence.
