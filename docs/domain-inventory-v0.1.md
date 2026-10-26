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

## Same-analyzer frozen-source comparison

The optional `--baseline-source-sha` path uses the **same installed
`analyze_domain_inventory` implementation and current mapping/role profiles**
for the immutable baseline and current source. The baseline tree is enumerated
with `git ls-tree` and content read via `GitReader.read_file`; the current
checkout must match the supplied exact SHA and have clean tracked changes.
The comparison records source-file/import-site count deltas, added/removed/
modified path witnesses, both source identities and the current analyzer SHA.
It is deliberately `NOT_EVALUATED` for design quality and public compatibility.

```bash
python3 .github/scripts/domain_audit.py \
  --sha "$(git rev-parse HEAD)" \
  --baseline-source-sha 6a6676e70ed60f440cfc00a878f24ef6ee2b91a5 \
  --output domain-inventory.json \
  --comparison-output domain-inventory-comparison.json
```

The Self Audit workflow uploads both JSON reports in
`codeqa-domain-inventory`. On `pull_request`, the default GitHub checkout
is a synthetic **merge revision**, not the raw PR head; report
`source_after_sha` and `analyzer_sha` must be read from the artifact/log
and must not be relabeled as the PR head. This CI witness is a merge-context
analysis, not independent direct-head execution or a human usability study.

The comparison also records added/removed **syntactic `__init__.py` import
candidates**. A removed candidate produces
`init_import_change_review.status=REVIEW_REQUIRED`, never a verified public
API break or a compatibility PASS. Candidate absence or incomplete source
coverage remains `NOT_EVALUATED`; dynamic `__getattr__`, reflection, re-exports
through other modules and actual downstream imports need independent review.

## Static metric-to-witness integrity (#119 incremental)

The before/after comparator now rejects an inventory whose claimed total,
intra-domain or cross-domain import-site counts disagree with its actual
`import_witnesses` array. Each witness must refer to selected source paths,
a positive source line and an explicit `INTRA_DOMAIN`, `CROSS_DOMAIN` or
`DOMAIN_UNKNOWN` classification. Missing witness coverage is an error,
not a zero-import or quality-improvement claim. Negative tests cover forged
counts, absent witnesses and foreign-source edges. This validates **internal
static evidence consistency only**; it cannot authenticate the GitHub
snapshot, prove semantic cohesion or measure human review burden.
