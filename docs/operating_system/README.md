# codeQA Samuel operating-system binding

**Consumer:** `HyungseonSong-plasma/codeQA`  
**Central authority:** `HyungseonSong-plasma/chatgpt-operation`  
**Expected OS:** Samuel  
**Immutable revision:** `b56b6cdc0d24f9a50e23165503ca6a4bbd70a771`

## codeQA-init

Start at [BOOTSTRAP.md](BOOTSTRAP.md). The pinned source and blob checks are
specified by [central_skills.json](central_skills.json). Read the central OS index,
essential rules, `session-bootstrap`, `state-refresh`, and the mandatory
`problem-oriented-response` README + machine contract at **that exact commit**.
Verify their recorded blob identities, along with the skill catalog and capability
registry. If the response skill or contract does not resolve, init fails closed as
`BLOCKED_RESPONSE_CONTRACT`.
For the requested always-ready branch-delete path, resolve
`GITHUB_BRANCH_DELETE` and load central `repository-mutation` as a
deliberate init-time immediate-obligation trigger.

Successful init reports `response_contract=samuel.problem-first-response.v1`,
`response_mode=problem_first`, `detail_policy=on_request`. After init, show
unresolved problems and exact human-review questions before optional details.

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

## Creation and pull-request routing

This explicit Samuel adoption registers GitHub file create/update, branch create and pull-request create, in addition to the existing PR merge, branch delete and workflow dispatch. Creation does not imply approval, and all QA/scientific contracts remain consumer-owned.
