# codeQA #92 — Samuel read-only handoff receiver

This is a bounded, versioned **live preflight** for a future Samuel
Controller action; it is **not** SDK conformance itself.

The receiver `.github/workflows/samuel-crossrepo-preflight.yml` has only
`contents:read` and `issues:read`. It validates:
- source `HyungseonSong-plasma/chatgpt-operation#220` and target
  `HyungseonSong-plasma/codeQA#92` using independent GitHub REST reads;
- exact `main` SHA and repository-qualified task identity;
- an allowlisted, authorized workflow dispatcher;
- on real `workflow_dispatch`, the independently fetched Samuel-origin
  Workflow Run's ID, event, source workflow path, SHA and actor;
- a structured target-run receipt with `allowed_mutations=[]`.

The same workflow executes on its installation PR with independent live
GitHub Issue reads, but explicitly stamps
`CONTROLLER_DISPATCH_UNVERIFIED` rather than claiming Samuel produced
that PR. A real `workflow_dispatch` receipt is distinguishable and can
be correlated with the originating Samuel `GITHUB_RUN_ID`.

No route accepts source write instructions, secrets, PR merge, automatic
issue closure, or claims about a production database schema. A codeQA
preflight `READ_ONLY_PREFLIGHT_CONFIRMED` is intentionally weaker than
a controller-origin implementation E2E. Subsequent work and issue closure
remain bound by #92's SDK/API/DB compatibility requirements and Samuel #220's
cross-repository authorization design.
