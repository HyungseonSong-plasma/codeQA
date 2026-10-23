# codeQA canonical architecture

**Status:** Adopted description of implementation boundaries; foundation Issue #1,
documentation slice #27. **Scope:** codeQA at
`main@21cea5bf0841f2049889877a340a1887bd7d8582` before this documentation
change. This document is **not** a declaration of full P1–P8 certification.

## Architecture and ownership

### End-to-end data flow

~~~text
Samuel / David (external orchestration)
    |
    | immutable caller-owned repository snapshot + snapshot identity,
    | selected files, quality profile and versioned contract data
    v
codeQA Python Pipeline (src/codeqa/pipeline/python.py)
    -> Python Adapter (AST syntax, no execution)
    -> Canonical Code Graph Core (CCG v0.1, facts and coverage)
    -> Shared Evidence + Static Dependency/Impact companions
    -> Mechanical v0.1 Evaluator (P1/P3 review heuristics only)
    -> Optional policy-grounded semantic/context/behavior companions
    -> Opt-in versioned QA Result v0.1 (scoped measurements/verdicts)
    -> Opt-in strictly comparable Quality Delta v0.1
    |
    v
Samuel / David (interprets evidence, decides subsequent actions)
~~~

There are **five separate concepts**; none can substitute for the next:

| Concept | What it means | Authority and limits |
| --- | --- | --- |
| **Source Snapshot** | Explicit selected source bytes and caller-provided immutable commit identity | External caller / Samuel owns acquisition, GitHub access and selection; codeQA does not independently attest snapshot completeness. |
| **Canonical Code Graph (CCG)** | Typed syntax-backed declarations/relationships, source provenance, resolved or unresolved targets, parse coverage | [CCG Core](../contracts/ccg/README.md) owns structure; graph facts **are not quality judgments**. |
| **Measured Finding** | Rule ID, numeric observation, unit, threshold, source witness | [Mechanical v0.1](mechanical-pipeline.md) evaluates line span and call-site count; a measurement is **not proof of a defect**. |
| **Semantic Judgment** | Interpretation under an *explicitly declared* role/policy and bounded evidence, possibly requiring human/domain review | [Semantic architecture](semantic-architecture-ontology.md), [directory roles](semantic-directory-roles.md) and [responsibility/behavior](responsibility-behavior.md) are separate, often **non-scoring** companions; no runtime truth inferred from a method name. |
| **Verdict** | Scoped per-rule or aggregate outcome with unsupported rules and limitations | [QA Result v0.1](contracts/qa-result-0.1.md): `PASS` means only observed rules on analyzed paths; `NOT_EVALUATED` is never silently promoted to PASS. |

### Responsibility and dependency direction

| Owner | Responsibility | Must not do |
| --- | --- | --- |
| [`chatgpt-operation` / Samuel](operating_system/README.md) | GitHub repository access, immutable snapshot acquisition, mutation, PR/workflow management, capability dispatch | Delegate mutation into codeQA evaluation modules. |
| [`infrastructure/`](codeqa-package-architecture.md) | Read-only local Git inspection and logical resource location; implementation plumbing | Evaluate Python AST or decide QA verdicts. |
| [`adapters/`](contracts/language-adapter-0.1.md) | Language-specific syntax extraction and typed Core records; Python adapter is AST-only | Execute inspected code or infer runtime dispatch from an unresolved syntax hint. |
| [`core/`](../contracts/ccg/README.md) | Immutable language-neutral CCG, dependency/evidence records and validation | Import Python ASTs, GitHub clients, evaluation rules or source-file discovery. |
| [`evaluation/`](mechanical-pipeline.md) | Pure measurements, explicit policy evaluation, evidence limits and separate public QA contract validation | Read/execute target repos, import Python Adapter ASTs, silently interpret static hints as runtime edges. |
| [`pipeline/`](efficient-evidence-pipeline.md) | Compose already-supplied parsed source, CCG, evidence, evaluator and optional views | Acquire target snapshots, orchestrate Samuel, or mutate GitHub. |
| [`governance/`](repository-structure.md) | Generic repository-policy integrity gates and frozen top-level layout enforcement | Substitute a local frozen root policy for another repository's profile. |
| [`profiles/`](../profiles/mechanical-v0.1.json) | Versioned concrete thresholds and repository-specific role/layout policies | Define universally applicable *facts* by a hard-coded repository name. |

Detailed package dependency direction is governed by
[package structure](codeqa-package-architecture.md); the root list is
independently [frozen](repository-structure.md). Optional cross-module
declaration candidates belong to [separate evidence](cross-module-symbol-evidence.md)
and do **not** become proven CCG runtime calls. Import paths and impact
are [potential static correspondence](dependency-impact.md), not lower or
upper bounds on runtime dependency effects.

## Normative contracts and their owners

| Contract | Canonical authority | Decision |
| --- | --- | --- |
| CCG v0.1 | [Schema](../contracts/ccg/graph-v0.1.schema.json) and [normative semantics](../contracts/ccg/README.md) | Existing `contracts/ccg/` is authoritative; original proposal `docs/contracts/ccg-0.1.md` is **satisfied by documented relocation**, not a duplicate copy. |
| Adapter capability v0.1 | [Adapter protocol](contracts/language-adapter-0.1.md) and [schema](../contracts/adapters/capability-v0.1.schema.json) | Supported, partial and unsupported input/output capabilities declared; Python has no hidden configurable include/exclude discovery. |
| Public QA Result v0.1 | [Normative result/delta semantics](contracts/qa-result-0.1.md), [result schema](../contracts/qa/result-v0.1.schema.json) and [delta schema](../contracts/qa/delta-v0.1.schema.json) | New **opt-in** contract, separate from older internal Python report serialization. |
| Semantic Architecture v0.1 | [Companion schema/vocabulary](../contracts/semantic/README.md) and [meaning](semantic-architecture-ontology.md) | Declared roles plus observed static relationships, not an omniscient code-quality predicate. |

Contract changes require a new version/ADR and positive/adversarial
conformance cases; frozen v0.1 artifacts are not silently reinterpreted.
See [ADR 0001](adr/0001-contract-authority-and-versioning.md).

## Python implementation and reproducibility

`analyze_python(sources, snapshot_id=..., ccg_schema=...,
mechanical_profile=...)` accepts an explicit in-memory mapping. One Python AST
parse per source produces CCG definitions, conservative import/call facts,
dependencies, shared evidence and optional impact/semantic views. Unknown
imports, aliases, call targets and missing files keep explicit uncertainty.
Most method and cross-file calls are **not** runtime resolved.

[Self-audit](self-audit.md) checks codeQA's own exact Git revision, with
separate production/test/all-Python scopes, and replays the **fixed historical
source SHA `6a6676e70ed60f440cfc00a878f24ef6ee2b91a5`** against current
analyzer code. It checks stable CCG/Mechanical observations on that input;
green CI is **not an independent proof of analyzer soundness**.

Independent reproducible reference evidence includes:

- [Samuel Python conformance](samuel-adapter-conformance.md), input commit
  `9b335e3fbb9c5e8e323e382daeec56fa25336822`, three byte-identical
  controller files and exact line/import controls.
- [MOOSE external Python audit](contextual-call-review.md), target commit
  `1977ad5559e5aa7a1c8d04c83735c15e007130d5`. Its architecture profile
  has explicit retrospective limitations, not a claim of native MOOSE
  semantics or execution.
- [Workflow guard](../.github/workflows/layout.yml) runs tests and the frozen
  layout policy check. The [self-audit workflow](../.github/workflows/self-audit.yml)
  adds historical evidence. Passing both is a regression gate, not proof of
  universal language support.

No unpinned live external repository content is silently accepted as fixture
truth. GitHub actions are executed by the external orchestrator, not by
`codeqa.core` or the evaluator.

## Evidence and decision rules

- CCG `coverage=complete` means parsed selected files, **not** semantic or
  repository completeness.
- `PASS` in Mechanical/QA Result means **only** the P1/P3 heuristics were
  measured on analyzed paths with no threshold review observations.
  `PASS` can coexist with `analysis=LIMITED` due to unresolved relationships
  or incomplete supplied source. A caller must preserve those limitations.
- `REVIEW_REQUIRED` is a candidate for contextual review, not proof of a
  principle violation. `NOT_EVALUATED`, unresolved targets and missing
  evidence are never promoted to PASS; `FAIL` has no currently-grounded
  generic Mechanical v0.1 failure semantics.
- The directory-role companion can identify explicit declared-policy
  violations; this cannot certify broad **P4 Separation of Concerns**.
- [Quality Delta](contracts/qa-result-0.1.md) is a *descriptive count of
  review-triggering observations* after strict compatibility checks; it does
  not certify increased change safety or fewer defects.

See [P1–P8 evidence map](engineering-principles.md) for per-principle
implementation status, profile applicability, counterexamples and future
evidence gates, and [ADR 0003](adr/0003-evidence-coverage-and-verdicts.md)
for the decision boundary. Future Rust conformance is tracked by
[Issue #30](https://github.com/HyungseonSong-plasma/codeQA/issues/30),
not claimed shipped here.
