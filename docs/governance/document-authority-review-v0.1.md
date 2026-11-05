# Documentation authority and responsibility — review v0.1

**Review scope:** codeQA `main@23c2166bd3b2b0c825b207e856b95c68e0e24070`,
[PR #289](https://github.com/HyungseonSong-plasma/codeQA/pull/289) and
[Issue #288](https://github.com/HyungseonSong-plasma/codeQA/issues/288).
The 109 initial PR-candidate Markdown pages were classified using their
titles, declared status, primary purpose and source/evidence references,
plus representative corroboration against the resource registry, code,
ADRs and issues. **This is a role/ownership review, not a full-body,
per-claim semantic certification of every historical document.**

## Source-of-authority hierarchy

| Role | What a reader may rely on | Actual authority |
| :-- | :-- | :-- |
| `NAVIGATION_INDEX` | Locate documents | Target artifact, not the index |
| `ACCEPTED_ADR` | Accepted decision in its recorded scope | [Accepted ADRs](../adr/0001-contract-authority-and-versioning.md) |
| `CONTRACT_EXPLANATION` | Human interpretation of typed exchanges | [Versioned contracts](../../contracts/README.md), validators and logical IDs |
| `POLICY_EXPLANATION`, `SCOPED_ADOPTION_POLICY` | Declared profiles or narrowly accepted policy | [Profiles](../../profiles/repository-layout.json), evaluators and recorded decision |
| `ADOPTED_ARCHITECTURE_GUIDE` | Architecture at the stated source revision | Code/ADR and frozen repository policy |
| `SCOPED_TECHNICAL_GUIDE` | Bounded documented feature | Matching source, tests and contract, not global QA PASS |
| `OPERATIONAL_RUNBOOK` | Pinned operator procedure | [Samuel binding](../operating_system/central_skills.json) and workflows |
| `PROPOSED_DESIGN` | Proposal/draft, not approval | No normative authority |
| `HISTORICAL_EVIDENCE` | Historical Git/run/fixture observation | Immutable historical witnesses, not present runtime |
| `SCOPED_DECISION_RECORD` | Named bounded milestone or no-go decision | That decision's exact accepted scope |
| `REVIEW_EVIDENCE` | Documentation routing rationale | This review's cited source snapshot only |

The catalog's `responsible_boundary` denotes a **proposed subject-matter
review group**, not confirmed CODEOWNERS, independent reviewer signatures
or a grant to mutate source. `authority_review=NOT_EVALUATED` continues
to mean full factual/claim-level corroboration is outstanding, even when
the **type of document authority** has been reviewed.

## Ownership conclusions

- **Architecture:** B1–B8 measurement/evaluation documents belong to
  `architecture/analysis/`; typed semantic roles and policy observations
  belong to `architecture/semantic/`. The current
  [architecture](../architecture.md) remains at its established entrypoint.
- **Naming vs integration:** [Python override/callback reflection](../python-override-callback-v02-draft.md)
  is limited runtime-binding evidence in `codeqa.evaluation.python_binding_runtime_v02`.
  [C++ override/compiler/MOOSE fixtures](../cpp-moose-naming-v02-draft.md)
  similarly belong to integration evidence. Neither is a general Naming
  glossary. Manual Rust lexical Naming stays under `quality/naming/`.
- **Contracts vs experiments:** [taxonomy decisions](../contract-taxonomy-and-composition-v0.1.md)
  belong to the explanatory `docs/contracts/` domain; the
  [schema composition no-go pilot](../schema-composition-pilot-v0.1.md)
  is an **experiment** and belongs with `docs/experiments/`. Schemas
  themselves remain normative only under `contracts/`.
- **Governance vs archives:** [branch reconciliation](../historical-branch-reconciliation-2026-11-05.md)
  is governance history, not justification for a standalone one-file
  `docs/evidence/` directory.
- **Samuel:** current `operating_system/` consumer runbooks are
  separate from archived [preflight receipts](../samuel/220-controller-preflight.md).
  A historical write proof grants no current authority.
- **Naming adopted versus pending:** [adopted v0.5 policy](../naming-official-policy-v05.md)
  covers only a narrow lexical scope. The [older proposal](../naming-official-adoption-v05-proposal.md)
  and other candidate glossary documents must not be presented as adopted
  wider semantic policy.

## Content-status reconciliation, still separate from routing

All states below were re-checked against issue/ref snapshots on 2026-11-05. The corresponding historical documents receive **dated reader updates**, preserving the original experiment assertions and scope. Such corrections are not full per-claim certification.

| File | Verified boundary | Content-renewal disposition |
| :-- | :-- | :-- |
| [B1–B8 design](../architecture-assessment-design-v0.1.md) | Issue #165 **closed/completed**, but document is historically *Proposed/design-only* | Keep historical design; link accepted implementation separately |
| [Naming coverage](../naming-coverage-v02.md) | #69 **closed/completed**; the earlier partial milestone said it did not close #69 | Preserve time-bound meaning; add dated later closure note |
| [Contract taxonomy](../contract-taxonomy-and-composition-v0.1.md) | #282 **closed/completed**, but future schema renames remain unapproved | Separate accepted terminology from deferred migration |
| [Workflow catalog](../workflow-catalog-v0.1.md) | 22 workflows are explicitly tied to an older Git revision, not current workflow count | Display prominently as historical snapshot |
| [Canonical architecture](../architecture.md) | Adopted guide pins an older source snapshot | Keep adopted-at-revision limit; refresh against code separately |
| [MOOSE archive](../experiments/moose-refactor-blind-versus-codeqa-20261023.md) | GitHub **still shows both** experiment branch refs at their recorded SHAs; the repository main has advanced from the 2026-10-23 baseline | Preserve immutable experiment evidence; clarify historical versus current main without implying branch deletion or merge |
| [Samuel preflight](../samuel/220-controller-preflight.md) | Already explicitly archival | Preserve warning |
| [Naming #144 draft](../naming-official-adoption-v05-proposal.md) | #144 **closed/not_planned**; narrower official v0.5 adopted independently | Classify as historical proposal, no broader policy authority |

The routing catalog records an explicit role for every current Markdown
document but does **not** rewrite historical prose or certify all its
claims. Before any relocation, finish exact incoming/outgoing path, fragment,
machine-reference and external deep-link audits. Existing stable entrypoints
and machine `docs/*.json` witnesses stay put. This review does not authorize
an 84-file move or a public-contract change.

**Result:** phase-1 authority-*type* and responsibility classification
review completed, with remaining per-claim acceptance and migration
review tracked under [#288](https://github.com/HyungseonSong-plasma/codeQA/issues/288).
