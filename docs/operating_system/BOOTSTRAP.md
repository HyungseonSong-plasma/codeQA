# codeQA cross-session bootstrap

**Command:** `codeQA-init`  
**Consumer:** `HyungseonSong-plasma/codeQA`  
**Expected OS:** Samuel

## Required sequence (no writes)

1. Verify repository identity and current default branch.
2. Read local `docs/operating_system/README.md` and
   `docs/operating_system/central_skills.json`; reject floating or mixed pins.
3. Fetch and verify the exact central `chatgpt-operation` commit
   `9b335e3fbb9c5e8e323e382daeec56fa25336822`; read the Samuel index, `ESSENTIAL_RULES.md`,
   `session-bootstrap` and `state-refresh` at this commit. Verify their
   expected blob SHA values before using them.
4. **Always** fetch and verify both `skills/catalog.json` and
   `skills/capability-registry.json` from the same pin; cross-check
   `GITHUB_BRANCH_DELETE` -> `repository-mutation` and the registry's
   provider ordering. Do not infer capability absence from connector visibility.
5. **Always** verify/read the central `repository-mutation` contract and
   inspect local `.github/workflows/samuel-branch-delete.yml`,
   `.github/requests/branch-delete-request.json` and their pinned Action
   binding. This eagerly primes the `GITHUB_BRANCH_DELETE` route; no
   deletion, dispatch, or mutation is performed by initialization.
6. Restore local codeQA authority from `README.md`,
   `docs/codeqa-package-architecture.md` and
   `docs/repository-structure.md`. Refresh active Issues/PRs, branch,
   CI and current work state. Select immediate work gate and load other
   Samuel skills only if triggered.
7. Report the exact pin, loaded sources, state, first gate and:
   ```text
   GITHUB_CAPABILITY_ROUTING=READY|BLOCKED
   GITHUB_BRANCH_DELETE_ROUTE=READY|BLOCKED
   GITHUB_MUTATION_PREFLIGHT=TRIGGER_REQUIRED
   ```
8. Stop **read-only**. A successful init is neither permission nor an
   automatic request to delete branches.

## Fail-closed contract

Mark routing `BLOCKED` if any required identity, verified central source,
catalog/provider mapping, or consumer execution route is absent/contradictory.
Distinguish routing-readiness from provider authorization/execution state.
When a later user mutation is requested, re-resolve `GITHUB_BRANCH_DELETE`
to Samuel `repository-mutation`, follow registry-ordered providers, obtain
fresh branch/SHA and permission evidence, and verify the postcondition.

For negative capability claims, resolve
`GITHUB_MUTATION_CAPABILITY_VERDICT` and use
`assert_capability_exhausted` rather than extrapolating a missing connector
operation. Rehydrate the same gate even after a context reset.

## Consumer execution route

Use `samuel-branch-delete.yml` only for an explicitly accepted deletion
request. It is permanently present and triggers after a change to the
version-controlled exact-SHA request manifest on protected `main`;
it may also be manually dispatched. The manifest is empty by default.
A request is a separate reviewed mutation; `codeQA-init` never edits it.
