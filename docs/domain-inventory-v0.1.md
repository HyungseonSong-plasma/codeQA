# Domain grouping audit v0.1 (Issue #119)

This is a **read-only, exact-source-SHA** companion to the existing Self Audit, not a
new quality principle or a proposal to relocate source files automatically.
`profiles/domain-grouping-v0.1.json` declares **filename hints**, not measured
semantic cohesion. `UNCLASSIFIED` and `AMBIGUOUS` are first-class outcomes.
The report records source file hashes/LOC, static import-site witnesses,
classified intra/cross-domain edges, unknown/dynamic import observations,
`__init__.py` import candidates, and potential reverse-import impact paths.
Existing `semantic-directory-roles-v0.1.json` forbidden-role rules are reused
without introducing an evaluation→adapter exception.

```bash
python3 .github/scripts/domain_audit.py --sha "$(git rev-parse HEAD)" --output domain-inventory.json
```

The exact-head `codeQA Self Audit` workflow stores the report as a separate
artifact. No inferred runtime call graph, human cognitive load, SRP proof or
maintainability score is emitted. A source-file count change is not a quality
improvement. Before/after comparison must use **the same analyzer and domain
policy** and pinned source revisions. `init_import_candidates` are merely
source-level witnesses; public compatibility and any package moves require
human review and independent import tests.

## Proposed migration decision

**Defer automatic migration.** Inspect cross-domain witnesses, unclassified
sources, public-import candidates and reverse-impact paths at a pinned SHA.
Only propose named, individually reviewable module moves after a concrete
consumer compatibility inventory and exact-head regression baseline exist.
Preserve CCG v0.1, Mechanical defaults and frozen QA Result v0.1. Unknowns
remain NOT_EVALUATED rather than being treated as evidence of isolation.
