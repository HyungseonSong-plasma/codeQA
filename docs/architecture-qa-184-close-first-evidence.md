# Architecture QA #184 — 43-edge evidence ledger and no-move review (2026-11-05)

**Scope:** bounded review of the existing #184 signal, parent #166; not a new automatic architecture proposal, migration approval, or QA PASS verdict.

## Source identities and artifact integrity

- Original B8: [run 40643089804](https://github.com/HyungseonSong-plasma/codeQA/actions/runs/40643089804), artifact `12796481475`; exact source `1f74db77c9940d3a1f688c6bcfb5ce34a91e4438`; ZIP SHA-256 `4b32472558c68fe5e8eee12120dd68d4991980d43f73354beca393a0618da0c0`.
- Later B8: [run 41771656076](https://github.com/HyungseonSong-plasma/codeQA/actions/runs/41771656076), artifact `13294538871`; exact source `ae13de79a89b7237eeeef8d91479cf76e51923e1`; ZIP SHA-256 `fb510cb65cab4bf4855f582ac7115cfd64dede4effb78ac4625dd27e7c4082cd`. Independently verified 16/16 manifest-listed file hashes and byte sizes.
- The two archives contain the **same 43 unique (source_path, target_path) pairs**. Some source bytes and line coordinates changed between snapshots; use the corresponding artifact's `source_sha256` and line evidence rather than mixing coordinates.
- The original B3 `CROSS_BOUNDARY_CONCENTRATION` is **43/48** outgoing Pipeline pairs (89.58%). This is a proxy and not an ownership verdict.

## Policy and bounded execution

- `profiles/semantic-directory-roles-v0.1.json` declares `pipeline` as the **composer of adapters, core and evaluators**. All 43 measured edges have `DECLARED_ALLOWED` direction; this is policy compatibility, **not** independent semantic proof.
- B8's bounded sample: **24/43** source-target pairs with direct Python calls (601 calls over 126 tests); **19/43** had no observed direct calls in that sample. Lack of a call is not dead-code or invalid-import evidence.
- The separate cold-interpreter observation records 43/43 import-line entries and 43/43 target-module path matches, but does not attest successful external consumer compatibility.
- Known internal test importing paths exist for each of these 43 source modules; they do not establish per-edge behavioral completeness. External/dynamic consumers, public API and semantic ownership are **NOT_EVALUATED**.

## Full measured pair ledger

All sources below belong to `pipeline`. The final column shows **bounded direct Python frame calls in the historical B8 sample**, not total runtime usage. A zero must not be interpreted as an unused dependency.

| # | Source path | Target path | Target role | Observed direct calls |
|---:|---|---|---|---:|
| 1 | `src/codeqa/pipeline/analysis_request.py` | `src/codeqa/adapters/python_snapshot.py` | adapters | 0 |
| 2 | `src/codeqa/pipeline/naming_field_evidence_v03.py` | `src/codeqa/core/naming_field_evidence_v03.py` | core | 0 |
| 3 | `src/codeqa/pipeline/naming_field_evidence_v03.py` | `src/codeqa/core/naming_review_worklist_v03.py` | core | 0 |
| 4 | `src/codeqa/pipeline/naming_field_evidence_v03.py` | `src/codeqa/infrastructure/git.py` | infrastructure | 0 |
| 5 | `src/codeqa/pipeline/naming_internal_import_census_v04.py` | `src/codeqa/core/naming_field_classification_v03.py` | core | 0 |
| 6 | `src/codeqa/pipeline/naming_internal_import_census_v04.py` | `src/codeqa/core/naming_internal_import_graph_v04.py` | core | 0 |
| 7 | `src/codeqa/pipeline/naming_internal_import_census_v04.py` | `src/codeqa/infrastructure/git.py` | infrastructure | 0 |
| 8 | `src/codeqa/pipeline/naming_official_adoption_v05.py` | `src/codeqa/core/naming_official_adoption_v05.py` | core | 2 |
| 9 | `src/codeqa/pipeline/naming_official_adoption_v05.py` | `src/codeqa/infrastructure/git.py` | infrastructure | 4 |
| 10 | `src/codeqa/pipeline/naming_official_policy_v05.py` | `src/codeqa/core/naming_official_adoption_v05.py` | core | 0 |
| 11 | `src/codeqa/pipeline/naming_official_policy_v05.py` | `src/codeqa/core/naming_official_policy_v05.py` | core | 1 |
| 12 | `src/codeqa/pipeline/naming_official_policy_v05.py` | `src/codeqa/infrastructure/git.py` | infrastructure | 2 |
| 13 | `src/codeqa/pipeline/naming_product.py` | `src/codeqa/adapters/python_naming.py` | adapters | 3 |
| 14 | `src/codeqa/pipeline/naming_product.py` | `src/codeqa/adapters/python_snapshot.py` | adapters | 3 |
| 15 | `src/codeqa/pipeline/naming_product.py` | `src/codeqa/core/naming.py` | core | 4 |
| 16 | `src/codeqa/pipeline/naming_product.py` | `src/codeqa/evaluation/naming.py` | evaluation | 3 |
| 17 | `src/codeqa/pipeline/naming_rule_inventory_v03.py` | `src/codeqa/core/naming_review_worklist_v03.py` | core | 0 |
| 18 | `src/codeqa/pipeline/naming_rule_inventory_v03.py` | `src/codeqa/core/naming_rule_inventory_v03.py` | core | 0 |
| 19 | `src/codeqa/pipeline/naming_rule_inventory_v03.py` | `src/codeqa/infrastructure/git.py` | infrastructure | 0 |
| 20 | `src/codeqa/pipeline/naming_scope_discovery_v04.py` | `src/codeqa/core/naming_scope_discovery_v04.py` | core | 0 |
| 21 | `src/codeqa/pipeline/naming_scope_discovery_v04.py` | `src/codeqa/infrastructure/git.py` | infrastructure | 37 |
| 22 | `src/codeqa/pipeline/naming_snapshot_coverage_v03.py` | `src/codeqa/core/naming_snapshot_coverage_v03.py` | core | 1 |
| 23 | `src/codeqa/pipeline/naming_snapshot_coverage_v03.py` | `src/codeqa/infrastructure/git.py` | infrastructure | 97 |
| 24 | `src/codeqa/pipeline/python.py` | `src/codeqa/adapters/python.py` | adapters | 46 |
| 25 | `src/codeqa/pipeline/python.py` | `src/codeqa/adapters/python_behavior.py` | adapters | 0 |
| 26 | `src/codeqa/pipeline/python.py` | `src/codeqa/adapters/python_context.py` | adapters | 46 |
| 27 | `src/codeqa/pipeline/python.py` | `src/codeqa/adapters/python_dependencies.py` | adapters | 46 |
| 28 | `src/codeqa/pipeline/python.py` | `src/codeqa/adapters/python_evidence.py` | adapters | 46 |
| 29 | `src/codeqa/pipeline/python.py` | `src/codeqa/adapters/python_snapshot.py` | adapters | 46 |
| 30 | `src/codeqa/pipeline/python.py` | `src/codeqa/adapters/python_symbols.py` | adapters | 46 |
| 31 | `src/codeqa/pipeline/python.py` | `src/codeqa/core/__init__.py` | core | 0 |
| 32 | `src/codeqa/pipeline/python.py` | `src/codeqa/core/behavior.py` | core | 0 |
| 33 | `src/codeqa/pipeline/python.py` | `src/codeqa/core/evidence.py` | core | 3 |
| 34 | `src/codeqa/pipeline/python.py` | `src/codeqa/core/function_context.py` | core | 2 |
| 35 | `src/codeqa/pipeline/python.py` | `src/codeqa/core/semantic_architecture.py` | core | 0 |
| 36 | `src/codeqa/pipeline/python.py` | `src/codeqa/core/symbols.py` | core | 3 |
| 37 | `src/codeqa/pipeline/python.py` | `src/codeqa/evaluation/contextual.py` | evaluation | 49 |
| 38 | `src/codeqa/pipeline/python.py` | `src/codeqa/evaluation/impact.py` | evaluation | 5 |
| 39 | `src/codeqa/pipeline/python.py` | `src/codeqa/evaluation/mechanical.py` | evaluation | 95 |
| 40 | `src/codeqa/pipeline/python.py` | `src/codeqa/evaluation/responsibility_behavior.py` | evaluation | 0 |
| 41 | `src/codeqa/pipeline/python.py` | `src/codeqa/evaluation/semantic_architecture.py` | evaluation | 0 |
| 42 | `src/codeqa/pipeline/source_coverage.py` | `src/codeqa/adapters/capability.py` | adapters | 11 |
| 43 | `src/codeqa/pipeline/source_coverage.py` | `src/codeqa/core/__init__.py` | core | 0 |

## B4 feasible-alternative audit

The later B8 artifact records **zero viable automatic virtual candidates**, three occupied destinations and two new role-policy violations. Do not invent a new target basename, bypass a collision, or treat virtual role relabeling as measured software improvement.

**Occupied targets:**

| Existing source in Pipeline | Rejected proposed destination | Why rejected |
|---|---|---|
| `pipeline/python.py` | `adapters/python.py` | Already occupied |
| `pipeline/naming_field_evidence_v03.py` | `core/naming_field_evidence_v03.py` | Already occupied |
| `pipeline/naming_official_policy_v05.py` | `core/naming_official_policy_v05.py` | Already occupied |

**Policy-rejected alternatives:** moving `pipeline/naming_internal_import_census_v04.py` into Core introduces Core imports to Infrastructure/Pipeline; moving `pipeline/naming_product.py` into Adapters introduces an Adapters-to-Evaluation import. These are **hypothetical** forbidden new dependencies, not violations in the existing pipeline.

## Independently justified, already merged structural cleanup (#187 / PR #188)

The original B8 observation was followed by an independently scoped source-backed
fix: [Issue #187](https://github.com/HyungseonSong-plasma/codeQA/issues/187)
and [merged PR #188](https://github.com/HyungseonSong-plasma/codeQA/pull/188),
merge commit `565bedc0bdf2cc9faf2f17f6e5ea1cc3ae5075b6`.
The adopted package architecture explicitly assigns all local Git subprocess
execution to `infrastructure.git.GitReader`, but two Pipeline source-selection
modules called Git directly. The merged change placed `tree_sha/tree_entries`
on the single read-only infrastructure adapter and retained public Naming
census entrypoints, exact Git tree identity and blob checks.

**Matched scope: the same 12 tracked `src/codeqa/pipeline/*.py` files.**

| Measured code fact | Before: `fb54b6c92363476b07a726008fbe8c1ab35f1a6a` | After: `6aa15e8613b95bf39233a7b191a730f257d7adb3` |
|---|---:|---:|
| Tracked Pipeline Python files | 12 | 12 |
| Pipeline modules importing `subprocess` | 2 | 0 |
| Direct Pipeline `subprocess` import sites | 2 | 0 |
| Git subprocess implementation owner | Pipeline and Infrastructure | Infrastructure only |

This exact-commit source comparison was independently read back from GitHub
for all 12 files, not inferred from a passing CI badge. Before, direct import
sites were `naming_scope_discovery_v04.py:14` and
`naming_snapshot_coverage_v03.py:9`; after, neither file imports
`subprocess`. PR #188 added `tests/test_git_tree_reader_v01.py`:
historical 95-file Git tree/blob denominator comparison, malformed/duplicate
record negative controls and a 12-file no-direct-subprocess regression;
the existing B8 E2E also tests the no-subprocess rule.

**Important measurement nuance:** this is a genuine source ownership cleanup
even though the B3/B8 cross-role import pair count remains 43/48. These are
different metrics. Do not describe unchanged import proxies as lack of the
observed Git subprocess improvement; do not claim the entire system is now
semantically optimal or that external public consumers have been attested.

## Bounded structural choice and acceptance limits

**Action for the 43 B8 import pairs: `NO_MOVE`. Assessment: `INSUFFICIENT_EVIDENCE` for unreviewed semantic ownership/external consumers.** Their source roles are composition-consistent and policy-allowed; no evidence-backed, noncolliding package move survived B4. A different, independently justified implementation-ownership cleanup **was completed by PR #188** and has a matched 2→0 direct Git subprocess import-site result. Avoid gaming the import ratio by moving package paths; retain the verified targeted cleanup benefit without claiming an unsupported package migration.

**Issue #184 disposition gate:** classify import-site roles and any suspected ownership leaks independently; record why KEEP/no move is favored over the rejected alternatives, including unresolved external consumers and test/API risks.

**Issue #166 product-outcome evidence:** the unprompted B8 signal/question pipeline and negative controls operate; an approved, independently bounded source cleanup was merged via #188, and the same 12-file source denominator now records 0 direct Git subprocess import sites versus 2 before. The current documentation-only PR triggers a fresh exact-head B8 run, which must be independently verified before claiming the final matched-scope self-audit. This demonstrates the specific ownership improvement, not universal semantic/API compatibility.

**Fresh re-audit evidence:** the documentation-only PR runs the existing B8 workflow at its exact proposed HEAD; verify the uploaded manifest and compare the 43 unique import pairs, 43/48 signal, B4 rejections and source-role scope against original B8. The 12-file direct-subprocess metric is independently verified above. A green B8 job alone does not prove architecture quality; unresolved consumers remain explicit.
