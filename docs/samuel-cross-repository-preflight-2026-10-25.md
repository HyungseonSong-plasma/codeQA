# Samuel #220 — isolated codeQA GitHub mutation preflight

**Status:** direct connector transport only; **NOT** a Samuel Controller-originated execution receipt.

## Target identity and isolation
- Target repository: `HyungseonSong-plasma/codeQA`
- GitHub repository ID: `1424293498` (connector-reported; must be checked again by any runtime executor)
- Branch: `samuel-220-crossrepo-preflight-20261025`
- Exact target main SHA at branch creation: `8832f1145b4e1ceb34928b725c071b5c4011b707`
- Change scope: this documentation witness only; no product source, workflows, secrets, or governance policies modified.
- Main merge: **not authorized**; deliberately leave PR unmerged.

## Evidence interpretation
This PR verifies that an explicitly authorized GitHub connector route can create a
branch, write a bounded file, open a PR and expose independently observable CI
on codeQA's exact PR head. It does **not** demonstrate that the Samuel
Controller, its `GITHUB_TOKEN`, or its ActionPlan executor can mutate codeQA.

The Samuel cross-repository capability issue is
[chatgpt-operation #220](https://github.com/HyungseonSong-plasma/chatgpt-operation/issues/220).
The draft validation guard is
[chatgpt-operation PR #223](https://github.com/HyungseonSong-plasma/chatgpt-operation/pull/223).
The target implementation work is [codeQA #92](https://github.com/HyungseonSong-plasma/codeQA/issues/92).

## Required next gate for true Controller-to-codeQA execution
1. An independently reviewable target opt-in policy pins **real** target repository
   ID, expected branch/head SHA, allowed paths, named workflows and operations.
2. Independently authenticated user authorization and target-token permissions
   are checked outside any Issue body or ActionPlan-supplied assertion.
3. A real Controller-produced, validated ActionPlan generates the bounded target
   mutation; missing/untrusted plans fail closed, and dispatch receipt IDs tie
   directly to the Controller invocation.
4. Check exact PR head SHA and every required non-skipped CI workflow result.
5. Preserve a separate reviewed merge grant; never conflate PR creation/CI
   with `main` merge permission.

If cross-repo credential or execution routing is unavailable, report
`NOT_EXECUTED` instead of treating this connector test as Controller E2E.
