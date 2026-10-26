# codeQA cross-session bootstrap

**Command:** `codeQA-init`  
**Consumer:** `HyungseonSong-plasma/codeQA`  
**Expected OS:** Samuel

## Required sequence (no writes)

1. Verify repository identity and current default branch.
2. Read local `docs/operating_system/README.md` and
   `docs/operating_system/central_skills.json`; reject floating or mixed pins.
3. Fetch and verify the exact central `chatgpt-operation` commit
   `cb785d898c624ba2b47fbb3d3840d48387605f47`; read the Samuel index, `ESSENTIAL_RULES.md`,
   `session-bootstrap` and `state-refresh` at this commit. Verify their
   expected blob SHA values before using them.
4. **Always** fetch and verify both `skills/catalog.json` and
   `skills/capability-registry.json` from the same pin; require the catalog's
   three mandatory `INIT` entries (`session-bootstrap`, `state-refresh`,
   `problem-oriented-response`). Cross-check `GITHUB_BRANCH_DELETE` ->
   `repository-mutation` and registry provider order. Do not infer capability
   absence from connector visibility.
9. **Always** load `skills/problem-oriented-response/README.md` and its
   `skills/problem-oriented-response/contract.json` at the exact central pin.
   Match both blob SHAs against `central_skills.json`; require
   `contract_id=samuel.problem-first-response.v1`, `mode=problem_first`,
   `detail_policy=on_request`, and `human_review_requires_question=true`.
   Missing or inconsistent response contracts mean `BLOCKED_RESPONSE_CONTRACT`;
   do not report initialization success.
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
   response_contract=samuel.problem-first-response.v1
   response_mode=problem_first
   detail_policy=on_request
   GITHUB_CAPABILITY_ROUTING=READY|BLOCKED
   GITHUB_BRANCH_DELETE_ROUTE=READY|BLOCKED
   GITHUB_MUTATION_PREFLIGHT=TRIGGER_REQUIRED
   ```
8. Stop **read-only**. A successful init is neither permission nor an
   automatic request to delete branches.

## Fail-closed contract

Mark routing `BLOCKED` if any required identity, verified central source,
catalog/provider mapping, or consumer execution route is absent/contradictory.
A missing or inconsistent mandatory response skill/machine contract blocks the
INIT result as `BLOCKED_RESPONSE_CONTRACT` and forbids normal post-init mode.
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

## GitHub mutation execution (separate from read-only init)

The exact pinned capability registry resolves `GITHUB_BRANCH_CREATE`, `GITHUB_FILE_CREATE`, `GITHUB_FILE_UPDATE` through `repository-mutation`, and `GITHUB_PR_CREATE` through `pull-request-create`. Resolve the owning skill, read the target branch/blob, use the registered provider order, and verify the resulting identity. `codeQA-init` remains read-only.
