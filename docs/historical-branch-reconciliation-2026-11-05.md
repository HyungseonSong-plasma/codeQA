# Historical branch history reconciliation — 5 November 2026

This document records the user-authorized integration of the remaining codeQA branches. The **working-tree source-of-truth remains current `main`**, not October's obsolete integration snapshots.

## Source reconciliation first

[PR #272](https://github.com/HyungseonSong-plasma/codeQA/pull/272) reviewed 10 outstanding historical/non-main refs and incorporated every file path absent from main (11 unique paths, 12 new files including one defensive test) without overwriting current code. It verified current `NOT_EVALUATED`/fixture language support declarations, retained historical Samuel preflights strictly as archives, and left native Samuel PR-creation admission **disabled**. Exact PR-HEAD checks succeeded **8/8**, including mandatory `layout`, isolated Python package and pinned conformance. After that merge, a Git tree comparison found **zero paths absent from current main** across all ten donor refs.

## Provenance-only history join

This integration commit has **current main as its first parent** and the following **ten exact historical branch HEADs as additional parents**. Conflicting paths intentionally keep the current validated main blob, not the old snapshot version. The commit introduces only this audit document to the reconciled main tree.

| Historical branch | Exact SHA | Disposition |
|---|---|---|
| `cleanup/merged-branches-b2-20261105` | `7960ea869085338b73baa111d8b290856fd170ad` | History retained; current validated main tree wins for previously existing paths |
| `codeqa/integration-118-120-123-125-20261026` | `3f84e40c3003b2f36e8f6a5b51ea9200b0c77d8f` | History retained; current validated main tree wins for previously existing paths |
| `codeqa/integration-119-124-93-20261026` | `dafd67e4130d571e58bbe5808839126899be343c` | History retained; current validated main tree wins for previously existing paths |
| `codeqa/integration-121-102-20261026` | `e476251d081811c880b0eb8fea59e7c785132919` | History retained; current validated main tree wins for previously existing paths |
| `codeqa/93-rust-parser-source-evidence-v01-20261025` | `b936819fcad009b740e38ecedc21e472f46c3cb9` | History retained; current validated main tree wins for previously existing paths |
| `issue-102-formal-implementation-binding-v01` | `a212319e4642913b26cb77542dbbac6c585af441` | History retained; current validated main tree wins for previously existing paths |
| `samuel/156-target-native-pr-executor` | `86ed941377e82540fd734c8184e246204f96d571` | History retained; current validated main tree wins for previously existing paths |
| `samuel/220-controller-crossrepo-preflight` | `0d0cd2afb1df05286a902920e2a46c9c47f4887f` | History retained; current validated main tree wins for previously existing paths |
| `samuel-220-crossrepo-preflight-20261025` | `3b12a741ed7d124b8189558c24cef5a8c1088c43` | History retained; current validated main tree wins for previously existing paths |
| `integration/reconcile-retained-branches-20261105` | `88bb53be3b355b244bb839b5927fbe9524519f0d` | History retained; current validated main tree wins for previously existing paths |

The 10 additional parents include the nine non-main refs present at the original request and the temporary #272 reconciliation branch. This is a **resolved Git-history merge**, not a blind replay of all obsolete file edits. The original unmerged historical PR records remain correctly `closed / not merged` in the GitHub PR API; they are not retroactively reviewed or marked merged. No source migration, semantic production authorization, Rust/C++ ABI approval or real Samuel Controller-origin cross-repository execution is inferred.

## After-merge verification and cleanup

Merge this audit-only history join through a protected-main PR after exact-head CI; subsequently verify every historical branch head is an ancestor of the new main in Git. Then the historical refs can be removed by the existing Samuel exact-SHA-guarded delete workflow, preserving their commits through merged history. GitHub Actions logs and artifacts remain separate audit evidence, not objects to erase.
