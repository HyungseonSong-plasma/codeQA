# Central Samuel skills — codeQA consumer

**Source:** `HyungseonSong-plasma/chatgpt-operation@cb785d898c624ba2b47fbb3d3840d48387605f47`

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

Samuel `cb785d898c624ba2b47fbb3d3840d48387605f47` registers `GITHUB_FILE_CREATE`, `GITHUB_FILE_UPDATE`, and `GITHUB_BRANCH_CREATE` through `repository-mutation`: `github-connector` first, then the bounded `repository-native` provider. `GITHUB_PR_CREATE` is handled by `pull-request-create` through `github-connector` only. Existing `GITHUB_BRANCH_DELETE` native-first and `GITHUB_PR_MERGE` guarded routes are unchanged. A successful create action does not certify CI, domain semantics, or human acceptance. Read exact target identities before and after any mutation; do not modify the capability registry with the native repository mutation workflow, whose protected policy explicitly denies that path.

## GitHub connector authorization and error triage

For a new GitHub write error, investigate **permissions and effective actor
identity early**, before proposing a new provider or a repository-native
workflow. Do not state a permission failure as fact without evidence:

- `GITHUB_PR_CREATE` is connector-only at the pinned Samuel revision. Verify
  the connector's accessible repository, branch/PR scopes and the exact target
  head/base before invoking it. An account with GitHub repository `admin`
  access is not proof that a particular Connector write or Actions token is
  authorized.
- A genuine GitHub HTTP `401/403/404` requires read-only verification of
  the acting identity, installation/token scopes, repository and branch
  Rulesets, and target existence. A `403` alone can indicate policy or
  authorization; label the cause `ACCESS_OR_RESOURCE_UNDETERMINED` until
  established.
- GitHub Actions `GITHUB_TOKEN` rights and the repository's
  `Settings → Actions → General → Allow GitHub Actions to create and approve
  pull requests` are relevant **only** when the failing route is Actions.
  Owner-reported setting changes do not prove an actual workflow's ability.
- `BLOCKED BY SAFETY SCREENING` is an **external tool-safety rejection**,
  not proof of GitHub permission failure. Do not retry the same logical write
  via a renamed path, different branch, alternate API or provider. Escalate
  to the originating screening authority and preserve the original refusal.
- Missing connector operation and a transient provider error are separate
  from an access denial. Resolve the pinned capability registry, classify
  the original failure, inspect prior same-intent blockers and verify the
  exact postcondition before declaring success, failure or global exhaustion.

When reporting an ambiguous failure, say: “This may be an authorization,
repository policy or provider issue. I will check the acting identity and
scoped permissions first; the root cause is not yet confirmed.”

For an upstream safety block, instead say: “The original tool rejected this
write during safety screening. No GitHub permission error was established,
and changing repository settings does not by itself clear the refusal.”
