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

## Bounded structural choice and acceptance limits

**Action: `NO_MOVE`. Assessment: `INSUFFICIENT_EVIDENCE` until independent domain judgment.** The observed module responsibilities are composition-consistent and policy-allowed. No evidence-backed, noncolliding alternative survived the measured B4 constraints, so there is no justified migration or matched before/after improvement claim. Avoid gaming a structural percentage by merely moving files or changing role labels.

**Issue #184 disposition gate:** classify import-site roles and any suspected ownership leaks independently; record why KEEP/no move is favored over the rejected alternatives, including unresolved external consumers and test/API risks.

**Issue #166 product-outcome gate:** the unprompted B8 signal/question pipeline and negative controls are implemented, but actual source cleanup, if supported, would need distinct approval and matched before/after evidence. An unsuccessful structural migration must not be fabricated to close #166.

**Fresh re-audit required:** these ZIPs are historical. The present documentation-only PR should cause the existing B8 workflow to run at its exact proposed HEAD; inspect that generated artifact and keep the original/current B1/B2/B3/B5/B7 denominators and limitations visible. B8 CI success alone never proves architecture quality.
