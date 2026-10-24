# ADR 0007 — Persistent cache safety before incremental semantic optimization

**Status:** Adopted for optional file-local CCG extraction cache v0.1,
2026-10-24, Issue #101.

## Context
A CCG snapshot may contain unresolved relationships and dynamic imports.
Static reverse-import traversal has no proven upper-bound semantics for
runtime dependencies. Reusing snapshot-wide QA/evidence or selecting an
incomplete affected-file subset could silently manufacture a clean Gate
or false improvement. A persistent cache can also introduce stale, corrupted
or cross-branch data.

## Decision
1. Do not persist ASTs, computed cross-file semantics, QA verdicts, CCG
   graph, policy decisions or formal/external evidence.
2. Persist only file-local syntax extraction with *exact* source digest,
   producer code/interpreter digest, explicit namespace, schema version and
   record checksum; bounded canonical JSON (never pickle).
3. Require trusted caller-owned isolated storage, POSIX file locking,
   atomic replacement, symlink protections, corruption fallback and eviction.
   Integrity hash is not independent cryptographic authenticity.
4. Always rebuild full selected-snapshot cross-file relationships, QA
   analysis, policy and evidence. The invalidation plan may describe
   *potential* affected modules but never authorize skipping verification.
5. Report `FULL_SNAPSHOT` fallback for unresolved dependencies, changed
   policies/toolchain/source selection, dynamic imports or untracked sources.
   `LOCAL_EXTRACTION_REUSE_FULL_SEMANTICS` permits syntactic reuse only.
6. Benchmark pinned codeQA source with cold/warm p50/p95, memory and full
   semantic oracle; do not promise a performance improvement or claim general
   monorepo scalability without independent evidence.

## Rejected
A new graph database, arbitrary persisted Python objects, implicit
cross-branch shared semantic cache, guessing dependency identity from an
import name, and optimistic omission of files from the PR analysis set.

## Follow-ups
#93 must supply real C++/MOOSE build-target metadata before selective
compiler invalidation. #94 retains cross-revision Naming semantics.
#98/#99/#100/#102 determine external evidence/Proof freshness, not this
file-local CCG cache.

**Tests:** `tests/test_persistent_ccg_cache_v01.py`.
**Benchmark:** `.github/scripts/incremental_ccg_benchmark.py`.
