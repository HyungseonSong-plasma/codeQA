# codeQA documentation

**Reader portal · Documentation routing, not a new source of contract authority.**  
See [documentation architecture and renewal gates](governance/documentation-architecture-v0.1.md) and the
[full Markdown inventory](documentation-catalog-v0.1.json).
The initial taxonomy keeps existing published document URLs in place; proposed
folders are **not claimed as completed migrations**.

## Architecture — what the system is and what is actually observable

- [Canonical architecture](architecture.md) — owners, CCG/evidence boundaries and supported interpretation.
- [Python package responsibilities](codeqa-package-architecture.md) — module ownership, not a proposal to relocate packages.
- [Architecture analysis B1–B8](architecture-assessment-design-v0.1.md) — discovery, hypotheses and migration-impact gates; distinguish *design proposal* from [implemented assessment](architecture-assessment-v0.1.md).
- [Semantic architecture ontology](semantic-architecture-ontology.md) · [Declared rules](declared-architecture-rules.md) — typed roles and explicitly declared policy, not actual runtime behavior.

## Quality analysis — measurements and reviewer decisions

- [Engineering principles and evidence limits](engineering-principles.md) · [Mechanical pipeline](mechanical-pipeline.md) — scoped QA rules, never universal P1–P8 certification.
- [Naming baseline](naming-conventions.md) · [Adopted Naming v0.5 scope](naming-official-policy-v05.md) · [Naming candidate and draft records](naming-review-worklist-v03.md).
- [Complexity](complexity-analyzer.md) · [Duplication](duplication-detector.md) · [Extraction-aware P3](extraction-aware-p3.md).
- [Static dependency correspondence](dependency-impact.md) · [Dependency metrics](dependency-metrics.md).

## Integrations — languages, SDKs and external tools

- [Python Adapter](python-adapter.md) · [Distribution and packaging](python-package.md) · [SDK conformance](python-sdk-conformance.md).
- [Language capability matrix](language-execution-matrix-v0.1.md) · [Mixed-source coverage](mixed-source-coverage.md).
- [Rust parser evidence](rust-parser-evidence-v0.1.md) · [C++ parser evidence](cpp-parser-evidence-v0.1.md).
- [Semgrep integration](semgrep-integration-v01.md) · [Pinned Dafny conformance](pinned-dafny-formal-conformance.md).

## Contracts — normative schemas versus explanatory texts

- [Canonical machine contracts](../contracts/README.md) — JSON Schemas, vocabulary and relevant validation boundaries.
- [Adapter contract explanation](contracts/language-adapter-0.1.md) · [QA Result explanation](contracts/qa-result-0.1.md) · [Quality Delta v0.2 explanation](contracts/quality-delta-0.2.md).
- [Contract taxonomy decision record](contract-taxonomy-and-composition-v0.1.md) · [Composition pilot and negative ROI](schema-composition-pilot-v0.1.md).

## Governance — accepted decisions, policy and verification

- [Accepted ADRs](adr/0001-contract-authority-and-versioning.md) · [Frozen repository layout](repository-structure.md).
- [Workflow catalog and historical provenance](workflow-catalog-v0.1.md) · [Self-audit](self-audit.md).
- [External evidence admission](external-evidence-v01.md) · [Evidence Gate](evidence-gate-v01.md).
- [Documentation responsibility and relocation rules](governance/documentation-architecture-v0.1.md) · [Authority/ownership review](governance/document-authority-review-v0.1.md).

## Samuel and historical evidence

- [Samuel consumer binding and bootstrap](operating_system/README.md) · [Pinned central skill manifest](operating_system/central_skills.json).
- [Controller preflight witness](samuel/220-controller-preflight.md) — archived, not an authorization of future writes.
- [Archived A/B experiments](experiments/README.md) · [Historical branch reconciliation](historical-branch-reconciliation-2026-11-05.md).
- [Architecture no-move evidence](architecture-qa-184-close-first-evidence.md).

## How to navigate this renewal

This portal is an **index**, not an endorsement of each linked document's
current applicability. Material marked *draft*, *proposed*, *historical* or
*opt-in* retains that status until its actual source/contract owner accepts
a change. Paths presently shown at the `docs/` root will be relocated
only by separately reviewed, link-safe migration batches.

For a new or significantly revised article, record its owner, scope,
source/evidence revision, status and canonical contract/profile link
before proposing a folder move. A new filename should never imply that
a proposal became implemented or that a JSON Schema is a quality verdict.
