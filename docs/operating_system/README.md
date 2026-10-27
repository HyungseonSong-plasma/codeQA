# codeQA Samuel operating-system binding

**Consumer:** `HyungseonSong-plasma/codeQA`  
**Central authority:** `HyungseonSong-plasma/chatgpt-operation`  
**Expected OS:** Samuel  
**Immutable revision:** `7b5b31e143474f4859fb6c85fb4a27afbad4eed3`

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


## Owner-requested branch cleanup batches (2026-10-27)

\`.github/requests/branch-delete-request.json\` is normally empty.
For explicit owner-authorized maintenance, a reviewed, short-lived nonempty
request may contain **at most 50** independently selected, exact-SHA pinned
non-default branch heads. \`validate_branch_delete_request.py\` rejects unsafe
names, duplicates, malformed SHA and default-branch deletion. The pinned Samuel
Action performs its own GitHub live HEAD lease check and verifies deletion.
A stale or moved branch must never be forced or treated as successfully removed.

The prior Layout assertion that the request **must always be empty** contradicted
the already installed workflow's supported nonempty request behavior. The test
now validates both the transient approved batch and the safe empty default;
this does not modify the actual manifest validator or delete contract.
After all targeted branch deletions have independent readback, restore
\`{"targets":[]}\` in a separate normal, reviewed maintenance commit.
Do not interpret any CI PASS or stale request as upstream safety-screening
clearance, and preserve unmerged branches/PR review records unless separately
dispositioned. The versioned workflow catalog and provenance remain unchanged.
