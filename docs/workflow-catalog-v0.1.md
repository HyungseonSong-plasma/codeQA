# Workflow governance catalog v0.1 (#124)

The [machine-readable catalog](workflow-catalog-v0.1.json) inventories **21
tracked workflows** at codeQA main `f7859c7f742ba55025bf1633ef7438d18e8a9416`.
The controller independently read GitHub repository ruleset **25360323**,
`codeQA-main-protection`, on **2026-10-25**. It was active on the default
branch and required exactly the job check `layout` (integration 15368), with
pull-request protection. Branch-protection endpoint itself returned 403;
the repository ruleset readback, not YAML naming, supports the observed
required-check claim. The live ruleset could subsequently change and is **not
re-fetched by unit tests**. CI only checks consistency with that dated readback.

`codeqa.governance.workflow_catalog` checks the actual Git-tracked workflow
paths, top-level trigger events, artifact-upload action counts, category, owner,
and the named required job. It fails closed on new/unclassified workflows,
retired paths, a fictional required check, changed triggers or an unsupported
retention guarantee. The existing Layout CI runs these tests. The manifest
classifies Samuel branch deletion, target executor and handoff as **operations**,
not product QA. Self Audit and external MOOSE audit are informational and not
branch-protection requirements. The catalog does not delete experiments,
change permissions, run workflows, or weaken any policy.

Artifact retention defaults and real branch protection at later SHAs remain
`NOT_EVALUATED` until independently read. A green conformance fixture is not
an end-to-end production support claim. Review stale entries and archived
experiments before retirement; preserve pinned SHA witnesses. Any workflow
addition, deletion or upload-action change must update this catalog in the
same reviewed PR.
