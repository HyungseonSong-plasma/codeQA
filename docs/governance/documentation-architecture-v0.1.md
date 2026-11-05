# Documentation information architecture v0.1 — scope and renewal gates

**Status:** Proposed for human review in [Issue #288](https://github.com/HyungseonSong-plasma/codeQA/issues/288); documentation-routing policy only.  
**Exact source snapshot:** `codeQA@23c2166bd3b2b0c825b207e856b95c68e0e24070`.  
**Initial scope:** 111 tracked `docs/` files: **107 Markdown + 4 JSON**; **89 Markdown** at the `docs/` top level before this proposal.

## Why the existing layout is hard to navigate

The root mixes architecture principles, B1–B8 architecture reports, ~two
dozen Naming-related records, language adapters, read-only experiments,
formal evidence, workflow metadata and Samuel coordination. Directories such
as `adr/`, `contracts/`, `experiments/`, `operating_system/` and
`samuel/` combine **document role, topic and organizational owner** at a
single level. A flat move by filename substring is not an architectural
classification: `architecture-assessment` assesses structural alternatives,
whereas `semantic-architecture-ontology` describes typed concepts and policy
declarations. Neither document is the other's normative authority.

## Two independent axes: responsibility and lifecycle

**Folders represent the primary *subject and owning boundary*.** Lifecycle
and authority are metadata *inside documents* and in their acceptance review,
not catch-all folders named `draft`, `old` or `final`:

| Proposed family | Responsibility | Typical subfamily |
| :-- | :-- | :-- |
| `architecture/` | Adopted structure, package ownership, static architecture questions and semantic ontology | `analysis/`, `semantic/` |
| `quality/` | QA observations and limitations: naming, Mechanical/P3, duplication, dependency evidence | `naming/`, `mechanical/`, `dependency/` |
| `integrations/` | Python/Rust/C++ adapter evidence, SDK and external tool interoperability | `python/`, `rust/`, `cpp/`, `tools/` |
| `governance/` | Frozen policies, provenance, security/authority gates, CI catalog and documentation maintenance | `evidence/`, `workflows/` |
| `contracts/` | **Human explanations** of versioned contracts and taxonomy, never extra normative JSON Schema copies | existing `contracts/` |
| `operating_system/` and `samuel/` | Consumer-specific operating-system pin/routing and controller integration receipts | existing stable directories |
| `experiments/` and `evidence/` | Completed experiments, historical comparisons and one-time source-backed decisions | existing experiment archive; proposed `evidence/` |
| `adr/` | Accepted architectural decisions | existing `adr/`, keep numbered files |

The physical proposal is recorded for **every Markdown file** in
[the complete catalog](../documentation-catalog-v0.1.json). That catalog is
a *routing and migration candidate inventory*, **not an attestation that the
document's claim or stated status has been independently verified**.
Docs [index](../README.md) is the reader entrypoint.

Each document must eventually receive distinct review decisions:
`lifecycle` (adopted/active/opt-in/draft/proposal/archived),
`authority` (normative contract explanation versus advisory interpretation
versus historical witness), `evidence_revision`, `primary_owner`,
`canonical_location`, and `external_deep_link_policy`. Until corroborated,
the catalog intentionally records authority review as `NOT_EVALUATED`,
never silently turns a draft into an approved contract.

## Canonical source and path invariants

- **Contract authority:** Published JSON Schemas live only under
  [`contracts/`](../../contracts/README.md); CCG v0.1 stays frozen.
  [Versioning ADR](../adr/0001-contract-authority-and-versioning.md)
  governs any schema location, `$id` or semantics migration.
- **Policy authority:** The repository-specific layout and thresholds live
  under `profiles/` or in the supplied consumer profile. Documentation does
  not override the frozen top-level [repository layout](../repository-structure.md).
- **Workflow authority:** The machine-readable `docs/workflow-catalog-v0.1.json`,
  `docs/workflow-provenance-v0.1.json`, and `docs/support-surface-v0.1.json`
  are *machine witnesses*, not prose articles. Do not relocate them without
  tracing exact paths in tests, source, workflows and root README generation.
- **Known stable entrypoints:** `docs/architecture.md`,
  `docs/engineering-principles.md`, `docs/repository-structure.md`,
  `docs/mechanical-pipeline.md`, and `docs/python-package.md` stay
  at their published URLs until their callers and GitHub fragments have been
  audited. A Markdown forwarding note is **not** an HTTP redirect and cannot
  guarantee preservation of `#fragment` deep links.
- **Claims:** An observed static relation is not a runtime dependency.
  CCG coverage is not full semantic coverage. A proposal, draft, archival
  benchmark or merely schema-valid result cannot be displayed as current
  implementation or universal PASS.
- **No duplicate authorities:** A moved document has one canonical text;
  never leave two divergent normative copies to keep old links alive.

## Evidence-based semantic consistency review queue

The following are **observed status/reference tensions**, not permission to
rewrite an authoritative claim in place:

| Document | Exact finding at baseline | Required reviewer decision |
| :-- | :-- | :-- |
| [Architecture assessment design](../architecture-assessment-design-v0.1.md) | Says *Proposed / Issue #165 / human architecture acceptance pending*, while GitHub Issue #165 is now **Closed · completed** | Decide whether this remains a historical design proposal or needs a separate current implementation guide. Do **not** silently equate issue closure with independent architecture acceptance |
| [Naming coverage v0.2](../naming-coverage-v02.md) | Says its bounded milestone **does not close #69**, but Issue #69 is now **Closed · completed** | Preserve the fact that the old milestone was partial; explain later acceptance by a dated addendum or a successor overview, without retroactively asserting its original scope was complete |
| [Contract taxonomy decision](../contract-taxonomy-and-composition-v0.1.md) | Labeled *Proposed* despite Issue #282 now **Closed · completed** with an explicit decision not to rename public v0.1 paths | Distinguish accepted reader-facing names from still-proposed future API/version migrations |
| [Workflow catalog prose](../workflow-catalog-v0.1.md) | Says **22** workflows at a pinned October snapshot; today's baseline tree includes **33** tracked workflow YAML files | Make the historical snapshot label conspicuous; use the current machine catalog/conformance for live status, not this older count |
| [Samuel preflight](../samuel/220-controller-preflight.md) | Historical bounded write proof already marked **archived** | Keep the archival warning and do not reinterpret it as current cross-repository write authorization |

These checkpoints require document-owner verification of the actual contract,
effective source revision, evidence scope, issue closure rationale and
runtime/CI acceptance. Rewriting dates or replacing `Proposed` with
`Implemented` merely because a GitHub issue is closed would be misleading.

## Controlled migration sequence

1. **Freeze and classify:** Record exact base commit and Git blob for every
   candidate; identify its purpose, maintainer, expected reader, public/normative
   status and evidence age. A filename pattern is a *candidate*, not proof.
2. **Impact audit:** Read **all tracked text**, not just Markdown: README links,
   HTML `href`, JSON/YAML registries, tests, CLI scripts, embedded file paths,
   heading slugs and GitHub Pages-style deep links. Record source and target
   paths, all incoming links, relative outgoing links and legacy anchors.
   Unknown external backlinks must be explicit uncertainty.
3. **Choose:** `STAY_STABLE`, `MOVE_WITH_VERIFIED_REFERENCES`,
   `REWRITE_IN_PLACE`, `MERGE_WITH_SINGLE_AUTHORITY`, or
   `ARCHIVE_WITH_PROVENANCE`. Do not delete or consolidate documents with
   contradictory or overlapping *scope* until consumer review.
4. **Execute one coherent family:** In one reviewed PR, relocate a bounded
   group, rewrite relative targets using old→new paths, update literal path
   dependencies, and verify every local target and `#fragment`. Preserve
   approved historical witnesses and git history. Existing GFM slugs must
   remain valid where promised.
5. **Verify exact PR head:** mandatory `layout` and relevant package,
   self-audit, contract, full documentation and workflow-provenance checks.
   Inspect actual GitHub rendering, review meaning/authority, and only then
   merge. A failed safety-screening or policy gate remains a hard stop.

## Present PR acceptance boundary

This **phase 1** only creates a portal, this taxonomy, a complete catalog and
a regression check. It does **not** move or delete the 107 existing Markdown
documents or the four JSON witnesses. The repository root and its published
paths/anchors remain unchanged. Subsequent migrations need individual
old→new path manifests, measured backlinks and independently reviewed PRs.

See [Issue #288](https://github.com/HyungseonSong-plasma/codeQA/issues/288)
for the renewal backlog and decision log.
