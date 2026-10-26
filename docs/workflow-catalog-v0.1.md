# Workflow governance catalog v0.1 (#124)

The [machine-readable catalog](workflow-catalog-v0.1.json) inventories **23
tracked workflows** on this Draft integration tree, based on codeQA main `f7859c7f742ba55025bf1633ef7438d18e8a9416`.
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

## Parallel PR integration witness (#119 / #124)

PR #128 changes `.github/workflows/self-audit.yml` from one to two
`actions/upload-artifact@v4` steps by adding `codeqa-domain-inventory`.
PR #130's catalog currently records **one** upload at the unchanged main
baseline. The concurrent changes therefore cannot be merged independently
without reconciling this exact entry; the Layout guard is expected to reject
the combined tree until the catalog's `artifact_upload_count` is updated
to **two** in the reviewed integration change. The
`test_workflow_catalog_cross_pr.py` regression exercises the mismatch, not
a simulated GitHub Actions success. Keep the category `experimental` and
`INFORMATIONAL_ONLY` artifact authority: the new domain inventory is
not required CI, a semantic design verdict or production authorization.

At merge review, refresh the current main revision, verify the actual YAML,
update the manifest in the same reviewed commit as the workflow change,
and rerun Layout at the **combined exact HEAD**. No automatic protection or
workflow setting mutation is authorized by this document.

## Tracked workflow source provenance

A companion [Git-blob manifest](workflow-provenance-v0.1.json)
records exact tracked SHA-1 Git blob identities for all 23 integration-tree workflows
at `f7859c7f742ba55025bf1633ef7438d18e8a9416`.
`codeqa.governance.workflow_provenance` independently recomputes each blob
identity from checked-out YAML and rejects changed, deleted, invented or
duplicate workflow entries. The pinned **retirement policy** is
`HUMAN_REVIEW_REQUIRED_PRESERVE_PINNED_EVIDENCE`: there is no automatic
deletion. This second manifest complements the category/trigger/required-check
catalog; a Git blob digest proves source-byte identity, **not** that any CI ran
successfully, that the file is branch-protected, or that an artifact is
semantically authoritative. Actual GitHub required-check status still needs
dated independent ruleset readback.

If PR #128's Self Audit upload change is approved, **both** the
`artifact_upload_count` field in the primary catalog and the matching
`blob_sha` in this provenance manifest must be updated within the same
reviewed integration change. The drift tests intentionally fail otherwise.

## Concurrent workflow changes awaiting merge reconciliation (2026-10-26)

This Draft integration tree classifies 23 workflows, including the new Rust
parser and Naming precedence jobs. Its exact Git blob provenance is valid
**only for this tree**. Separate Draft PR #140 changes
`.github/workflows/python-package.yml` for installed-wheel Pyright, and
Draft PR #141 changes `.github/workflows/pinned-dafny-formal.yml` for a
read-only GitHub run/source relation check. Those two workflow blobs differ
from the hashes currently recorded here. Green independent PR checks do not
make the three source trees mutually compatible or merge-ready.

Reviewers must select an explicit integration order, incorporate the final
workflow bytes, update both manifests in the same reviewed change, and run
Layout and the relevant conformance jobs against the resulting combined tree.
No self-approval, ruleset change or automatic merge follows from this note.

## Required status-context uniqueness guard (#124 incremental)

The source audit now requires **exactly one** `name: layout` job context in
the observed required workflow. A second job with the same required status
name is rejected as ambiguous even if the GitHub ruleset still lists
`layout` and all workflow paths remain classified. The negative fixture
appends a second named job and expects the catalog guard to fail. This is a
static source constraint; live GitHub ruleset readback and exact-head CI are
still separate obligations.

## Required-check shadowing and execution guard (#124)

The catalog now rejects a non-required workflow that shadows the protected
`layout` context through either a job ID or an explicit job name. The required
job must retain an unfiltered `pull_request` trigger, no job-level conditional
or dependency, no ignored step failures, and the actual unit/semantic-layout/
frozen-policy guard commands. Adversarial tests remove or bypass each guard.
This is a **static, repository-specific YAML constraint**, not proof that
GitHub ran the job or a replacement for independently read ruleset status.

## Combined-tree integration candidate (#139 + #140 + #141)

This **Draft PR** now includes the exact source blobs of Draft #140
(`9ac926ed54e4781bd046e5333a93b8adc7ebc29f`) and Draft #141
(`5c660ec5cbc8739817bcc6ae19e9a35fc0e16dcc`) in addition to the
#119/#124/#93/#91/#122 integration. Both changed workflow identities
(`python-package.yml` and `pinned-dafny-formal.yml`) are reconciled
in the same atomic Git tree as the source and tests. This supersedes
the earlier *unreconciled* parallel-PR warning **for this combined tree only**.
Exact combined-head Layout, package, Rust/C++, Dafny and authority CI
must be independently witnessed before any merge consideration.

Constituent Draft PRs remain unmerged and must not subsequently be
merged on top of the integrated tree as duplicate overlapping changes.
Human review, repository ruleset readback and issue-level original
acceptance gates remain separate; the combined test PR does not confer
production Formal, Naming, SDK, ABI or migration authority.

## Upstream MOOSE source lock integration (#93)

This combined Draft now also incorporates #93 source PR #137's upstream
`idaholab/moose@9f388366ccf38b9c34542ec5561198249fde0ac9`
**three-file source identity** witness, tied to the pinned application
`physics_app/dependencies.lock` and exact Git blob identities.
`mixed-source-conformance.yml` is re-pinned to blob
`d2d76c5853ca4b0a4ac9f81164efaa2a87622acb` in this same
integration tree; its artifact upload count remains **one**.
A real source fetch and negative checks are required in mixed-source CI.
This is NOT upstream release/ABI, DSL grammar, parameter semantics or
production compatibility evidence; those remain `NOT_EVALUATED`.

## Pinned MOOSE HIT parser source extension (#93)

The upstream source lock now covers **eight** exact files at the same
pinned `idaholab/moose` commit, including `MooseSyntax.h`, `Syntax.C`,
HIT `lex.cc`, HIT `parse.cc` and HIT `parse.h`.
The modified `mixed-source-conformance.yml` Git blob is
`b5cc3fd22572a8181e05b2ffb1b42d566664035c`; the single artifact
upload still contains only **source/controlled-compiler receipts**.
This remains NOT_EVALUATED for executed input DSL grammar, reserved
parameter naming, framework release, public ABI and deployment.
