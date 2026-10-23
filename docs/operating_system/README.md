# codeQA Samuel operating-system binding

**Consumer:** `HyungseonSong-plasma/codeQA`  
**Central authority:** `HyungseonSong-plasma/chatgpt-operation`  
**Expected OS:** Samuel  
**Immutable revision:** `9b335e3fbb9c5e8e323e382daeec56fa25336822`

## codeQA-init

Start at [BOOTSTRAP.md](BOOTSTRAP.md). The pinned source and blob checks are
specified by [central_skills.json](central_skills.json). Read the central OS index,
essential rules, `session-bootstrap`, `state-refresh`, catalog and capability
registry at **that exact commit**, verifying the recorded blob identities.
For the requested always-ready branch-delete path, resolve
`GITHUB_BRANCH_DELETE` and load central `repository-mutation` as a
deliberate init-time immediate-obligation trigger.

Report `GITHUB_CAPABILITY_ROUTING=READY|BLOCKED` and
`GITHUB_MUTATION_PREFLIGHT=TRIGGER_REQUIRED` independently of the visible
GitHub connector tools. Init is **read-only** and never deletes a branch.
A missing connector operation is not global Samuel capability exhaustion.

## Boundaries

codeQA owns the CCG, adapters, source evidence, QA profiles and local
repository acceptance policy. Samuel owns generic skill/capability routing,
GitHub mutations and postcondition mechanics. Neither a successful init nor a
green unit-test check authorizes or executes a mutation.

Current work state is the live repository ref, open Issues/PRs, and relevant
CI/Actions evidence, not remembered chat state or a historic report.
Do not create any new root entry; the codeQA frozen root layout is unchanged.

The permanent consumer execution path is
`.github/workflows/samuel-branch-delete.yml`, consuming
`.github/requests/branch-delete-request.json`. The obsolete one-shot cleanup
workflow is retired. See [CENTRAL_SKILLS.md](CENTRAL_SKILLS.md).
