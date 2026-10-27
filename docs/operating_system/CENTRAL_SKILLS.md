# Central Samuel skills — codeQA consumer

**Source:** `HyungseonSong-plasma/chatgpt-operation@b56b6cdc0d24f9a50e23165503ca6a4bbd70a771`

## Required init

Verify/read from the exact source revision and recorded blob SHA:

- `docs/operating_system/README.md` and `ESSENTIAL_RULES.md`
- `skills/session-bootstrap/README.md`
- `skills/state-refresh/README.md`
- `skills/problem-oriented-response/README.md` and its
  `skills/problem-oriented-response/contract.json` (mandatory `INIT`;
  `samuel.problem-first-response.v1`, `problem_first`, `on_request`)
- `skills/catalog.json` and `skills/capability-registry.json`
- `skills/repository-mutation/README.md` (eagerly trigger-loaded for
  `GITHUB_BRANCH_DELETE` readiness only, without mutation)

The machine-readable pin and expected blob identities belong to
`docs/operating_system/central_skills.json`. Do not mix revisions or
silently follow `main` / `latest`. The response skill and machine contract must
both match the pinned blobs; otherwise report `BLOCKED_RESPONSE_CONTRACT`.

## Always-ready deletion routing

```text
codeQA-init -> central Samuel exact pin verified
  -> GITHUB_CAPABILITY_ROUTING=READY
  -> GITHUB_BRANCH_DELETE -> repository-mutation
  -> capability registry: repository-native (priority 10)
     then github-connector (priority 20)
  -> persistent consumer workflow: samuel-branch-delete.yml
  -> request manifest: .github/requests/branch-delete-request.json
```

This is *routing readiness*, not provider execution readiness or permission
to delete. When deletion is actually requested, refresh the branch identity,
owner/authorization, and permissions; use exact expected SHA and Samuel's
read-before / delete / read-after guard. Do not delete `main`.
An absent target is a verified `NO_MUTATION_NEEDED`; a mismatched SHA
hard-stops. A connector lacking delete does not establish global unavailability.

For an unavailability claim, resolve `GITHUB_MUTATION_CAPABILITY_VERDICT`
through `repository-mutation` and apply registry-ordered evidence and
`assert_capability_exhausted` before issuing a global negative verdict.
After context loss, rehydrate the central trigger, skill and provider mapping
from exact pinned evidence rather than chat memory.

Other skills load only when triggered (e.g., `GITHUB_PR_MERGE`,
`GITHUB_ACTIONS_EXECUTION`, `GITHUB_ACTIONS_OBSERVATION`).

## GitHub creation and update routing

Samuel `b56b6cdc0d24f9a50e23165503ca6a4bbd70a771` registers `GITHUB_FILE_CREATE`, `GITHUB_FILE_UPDATE`, and `GITHUB_BRANCH_CREATE` through `repository-mutation`: `github-connector` first, then the bounded `repository-native` provider. `GITHUB_PR_CREATE` is owned by `pull-request-create`: `github-connector` (priority 10) with guarded `repository-native` (priority 20) via `samuel-controller.yml` and `samuel-native-github.yml`. Safety-screening and policy denials are hard stops, not fallback triggers. Native registration does not authorize merges, policy exceptions, or clearing historical blockers. Existing `GITHUB_BRANCH_DELETE` native-first and `GITHUB_PR_MERGE` guarded routes are unchanged. A successful create action does not certify CI, domain semantics, or human acceptance. Read exact target identities before and after any mutation; do not modify the capability registry with the native repository mutation workflow, whose protected policy explicitly denies that path.
