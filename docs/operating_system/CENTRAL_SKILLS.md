# Central Samuel skills — codeQA consumer

**Source:** `HyungseonSong-plasma/chatgpt-operation@28abfb4d640e433818f3a9f75312721f9f195a52`

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

## Documentation refinement v0.2 (on demand)

`DOCUMENTATION_REFINEMENT` selects pinned
`skills/documentation-refinement/README.md` plus
`skills/documentation-refinement/contract-v0.2.json`
(`samuel.documentation-refinement.v0.2`). The legacy `contract.json` and
`refine_document()` call without a diagram remain available. v0.2 adds a
read-only Markdown anchor/readability audit and an **opt-in**, source-witnessed
Mermaid diagram renderer (`diagram=...`), with explicit limits on semantic
claims. It does **not** prove semantic equivalence, modify GitHub, or run on `INIT`.
CodeQA owns interpretation of its schemas, profiles and reports.
Apply accepted changes through Samuel's separately authorized file/PR routes,
with exact-head validation and review.

## Documentation Consistency QA v0.1 (Phase B, on demand)

`DOCUMENTATION_CONSISTENCY_QA` now resolves the pinned
`skills/document-consistency/README.md` and
`skills/document-consistency/contract-v0.1.json` with exact Git blob SHA
verification at the **same** Samuel revision as the required INIT skills.
Contract identity: `samuel.documentation-consistency.v0.1`. The execution
mode is **`READ_ONLY`** and activation is **`trigger`**, never `INIT`
or an unattended Controller job.

**On an explicit documentation-status QA request:**
1. Resolve `document-consistency` from `central_skills.json` and the
   exact pinned central catalog; reject mismatched source revision, Git blobs,
   contract ID, trigger, read-only mode or unexpected status vocabulary.
2. Read the codeQA-owned `docs/documentation-catalog-v0.1.json` as
   **declared metadata**, not independent review authority. The pilot
   currently identifies only two `status_labels` documents:
   `docs/architecture.md` and
   `docs/governance/documentation-architecture-v0.1.md`.
3. Run the local, **read-only pilot presentation check** from codeQA root:
   `python3 -m unittest discover -s tests -p 'test_document_status_badges.py' -v`.
   It checks each pilot document's declared status values, H1 badge placement
   and local SVG assets. The rest of the documentation catalog is not
   silently assigned statuses or treated as passed.
4. For Samuel's portable `audit_document_labels` API, the caller must
   separately provide exact source bytes, a 40-hex snapshot revision and
   **complete** source inventory, as required by its contract. The local
   pilot test alone does **not** attest that full-source witness.
5. Report **presentation MATCH/MISMATCH separately from semantic status**.
   A green check means the declared labels were displayed consistently:
   `semantic_status=NOT_EVALUATED` and
   `authority_upgrade=FORBIDDEN`. The optional scoped static Gate 1
   result is not Gate 2 approval. Gate 2 independently remains
   `REVIEW_REQUIRED` until authenticated domain review is completed.

The command performs no GitHub writes, pin upgrades, document migrations,
automatic badge edits or mutations. Any later proposed edit requires a
separate reviewed, target-bound codeQA mutation path. Samuel #264's generic
cross-repository native mutation is **still unsupported**.

## GitHub creation and update routing

Samuel `28abfb4d640e433818f3a9f75312721f9f195a52` registers `GITHUB_FILE_CREATE`, `GITHUB_FILE_UPDATE`, and `GITHUB_BRANCH_CREATE` through `repository-mutation`: `github-connector` first, then the bounded `repository-native` provider. `GITHUB_PR_CREATE` is handled through `pull-request-create` using **`github-connector` only**. Safety-screening and repository policy denials are hard stops, not permission diagnostics or fallback triggers. Existing native-first `GITHUB_BRANCH_DELETE` and guarded `GITHUB_PR_MERGE` routes remain unchanged. GitHub permission diagnosis must use original error evidence; never assert an upstream screening block is a GitHub 403.

## Phase A consumer execution boundary (Samuel Issue #264)

This exact-revision pin verifies Samuel **source identities and routing metadata**;
it does not turn every catalog entry into an approved codeQA execution provider.

- `codeQA-init` remains read-only. Resolving `GITHUB_FILE_CREATE`,
  `GITHUB_FILE_UPDATE`, or `GITHUB_BRANCH_CREATE` from the central catalog is
  **routing discovery**, not permission to execute.
- The Samuel `REPOSITORY_MUTATION` gateway/native workflow uses
  `automation/samuel/repository-mutation-policy.json` bound to
  `HyungseonSong-plasma/chatgpt-operation`. It is **not a supported provider
  for codeQA-targeted generic file/branch mutation** at this pin. Without a
  separately verified, target-repository policy and authorized execution
  provider, stop as `TARGET_POLICY_NOT_ESTABLISHED`; do not dispatch the
  Samuel native workflow or substitute its policy for codeQA.
- The central catalog lists the `github-connector` before the native
  mutation fallback. Such a provider can be considered only after its own
  original safety screening, codeQA-targeted policy, actor permissions,
  expected SHA and postcondition gates pass. An upstream refusal is a hard
  stop; do not try the native provider to evade it.
- Existing codeQA `.github/workflows/samuel-branch-delete.yml` is a
  **separate target-owned exact-SHA path**, requiring an explicit reviewed
  request. Its pinned Action and underlying deletion module are byte-identical
  across the old/new Samuel revisions. Initialization never dispatches it.
- The target-owned Issue #92 `samuel-codeqa-issue-execute.yml` has a separate,
  narrow local policy `profiles/samuel-issue92-target-executor-v1.json`;
  that policy remains `enabled=false`. It is not evidence that the generic
  Samuel cross-repository gateway is ready.
- Samuel [Issue #264](https://github.com/HyungseonSong-plasma/chatgpt-operation/issues/264)
  tracks proper target-bound native-policy design independently. Until its
  evidence is accepted, do not promote any consumer mutation readiness claim
  based on this pin upgrade or green CI.

Documentation Consistency QA remains **Phase B**, separately activated after
this pin migration. Gate 2 independent semantic approval stays
`REVIEW_REQUIRED`; no documentation badges gain review status automatically.

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
