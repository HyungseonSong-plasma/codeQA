# Contract taxonomy and composition — issue #282

**Status at drafting:** Proposed, evidence-scoped design; public contract renames are **not** approved by this report. **Decision update (2026-11-05):** Issue [#282](https://github.com/HyungseonSong-plasma/codeQA/issues/282) is closed/completed for bounded taxonomy decisions. The [two-contract composition pilot](schema-composition-pilot-v0.1.md) was completed with a **no-go** for a new framework at the measured scope; the optional Mermaid renderer was merged in [Samuel #248](https://github.com/HyungseonSong-plasma/chatgpt-operation/pull/248) and adopted in codeQA [#287](https://github.com/HyungseonSong-plasma/codeQA/pull/287). Existing v0.1 IDs and paths were **not renamed**.  
**Evidence snapshot:** `codeQA@e7542de9f55eca5de26121bba3e11cd2b27c3066` (2026-11-05).  
**Owner:** codeQA; [plan #282](https://github.com/HyungseonSong-plasma/codeQA/issues/282).  
**Related authority:** [ADR 0001](adr/0001-contract-authority-and-versioning.md), [package boundaries](codeqa-package-architecture.md), and the [contract catalog](../contracts/README.md).

## Evidence inventory: measure before renaming

The exact tracked Git tree contains **37 contract JSON documents** across four
existing families. This is a **file inventory**, not a finding of 37 unique
semantics or a computed duplication percentage:

| Family | JSON Schema documents | Vocabulary documents | Bytes of tracked JSON | Primary responsibility |
| :-- | --: | --: | --: | :-- |
| `contracts/adapters/` | 2 | 0 | 8,188 | Adapter declaration and source-selection exchange |
| `contracts/ccg/` | 1 | 0 | 7,283 | Canonical graph facts and coverage |
| `contracts/qa/` | 29 | 0 | 160,734 | Measured findings, architecture-analysis evidence and decisions |
| `contracts/semantic/` | 4 | 1 | 15,408 | Ontology and declared-policy companion reports |
| **Total** | **36** | **1** | **191,613** | Versioned consumer contracts |

Counts are based on Git blob sizes, using the path/suffix inventory at the
pinned revision. They exclude README files and `profiles/`. A rise in counts
may indicate feature growth rather than duplication; maintain a versioned
denominator and measure maintenance burden independently.

## Decision A — disambiguate the two architecture concepts

The name `architecture` is currently overloaded, but the contracts do **not**
describe the same kind of evidence:

| Existing path | Intended meaning | Authority / limit | Reader-facing name |
| :-- | :-- | :-- | :-- |
| [`qa/architecture-assessment-v0.1.schema.json`](../contracts/qa/architecture-assessment-v0.1.schema.json) and seven related QA architecture schemas | Evidence-first source inventory, static metrics, candidate scenarios, migration impacts and bounded architecture recommendations (B1–B8) | `codeqa.evaluation.architecture`: **analysis/evaluation** of possible layout choices, not proof of optimal structure | **Architecture Analysis** |
| [`semantic/architecture-v0.1.schema.json`](../contracts/semantic/architecture-v0.1.schema.json) and [vocabulary](../contracts/semantic/architecture-v0.1.vocabulary.json) | Typed ontology entities, relations, policy declarations and bounded observations | `codeqa.core.semantic_architecture` plus pure projector, **semantic model**; not a scored quality decision | **Semantic Architecture Ontology** |
| [`semantic/declared-rule-policy-v0.1.schema.json`](../contracts/semantic/declared-rule-policy-v0.1.schema.json) and rule report | Declared role constraints and evidence-scoped violations | Policy/configuration and explicit rule evaluation, not observed runtime behavior | **Declared Architecture Rules** |

**Adopt the three reader-facing labels now** in catalog/navigation. Preserve
the already published path names and public JSON `$id` values. A new v0.2
contract **may** adopt an `architecture-analysis-*` prefix for QA and
`semantic-ontology-*` for ontology only after an accepted ADR with alias,
consumer migration and fixture checks; do not rename existing v0.1 files in
place. A path move must retain exactly one normative schema authority and
existing logical resource IDs or migrate them deliberately.

The analysis/syntax distinction is substantive: importing a file, observing a
source symbol, declaring a prohibited dependency and recommending a new module
boundary are four different claims.

## Decision B — suffixes describe artifact kind, not popularity

The one [`.vocabulary.json`](../contracts/semantic/architecture-v0.1.vocabulary.json)
is **not** a failed schema classification merely because it is unique:

- `*.schema.json`: JSON Schema (currently Draft 2020-12 in sampled contracts)
  describing **permitted instance shape**, required fields and constraints.
- `*.vocabulary.json`: a codeQA-specific **closed ontology term registry**
  (entity kinds, typed relation endpoints, assurances and assessment states).
  It is **not** a formal JSON Schema or an RDF/OWL vocabulary; do not load it
  as a JSON Schema.
- `profiles/*.json`: repository/application policy values; a profile may be
  schema-validated but is not itself the schema.
- `docs/*.md`: explanatory, non-normative navigation unless an ADR explicitly
  declares authority. Do not clone published schemas under `docs/`.

The [semantic ontology tests](../tests/test_semantic_architecture_ontology.py)
check vocabulary terms against the Core and schema and verify typed edge
endpoints. The vocabulary therefore has **current distinct operational value**.
Do not merge its lists into the schema by naming convention alone.

**Future choice:** retain a separate vocabulary while ontology terms are read
independently. If a future revision establishes schema as the **single**
authoritative source of enums, derive vocabulary deterministically from that
pinned schema with exact equality tests and independent consumer compatibility
review; never maintain two drifting authorities. This requires actual semantic
equivalence evidence, not a textual key-name match.

## Decision C — a composition framework, not a new directory explosion

Several architecture QA contracts repeat *field names* including
`schema_version`, `snapshot_sha`, `inventory_id`, `coverage`, and
`limitations`. This is a **candidate common denominator**, not proof that
their validation rules can be shared. For example:

- [Architecture metrics](../contracts/qa/architecture-metrics-v0.1.schema.json)
  declares five local `$defs` (`git_sha`, `sha256`, `count`,
  `nullable_ratio`, `witness`) and many **local** `$ref` references.
- [Architecture inventory](../contracts/qa/architecture-inventory-v0.1.schema.json)
  declares `sha256` and `counts` locally.
- [Architecture opportunities](../contracts/qa/architecture-opportunities-v0.1.schema.json)
  declares `witness`, `signal` and `opportunity` locally.
- [Architecture assessment](../contracts/qa/architecture-assessment-v0.1.schema.json)
  is a single versioned report shape with **different required fields**.
- None of these four inspected contracts uses an external `$ref`; blindly
  replacing local references with cross-file references risks breaking
  standalone validators, installed packages and offline consumers.

**Recommended framework:** an *internal, deterministic schema-composition
toolkit* for **future revisions only**, driven by typed primitives such as
`GitCommitSHA`, `EvidenceDigest`, `SourceScope`, `Coverage` and
`Limitations`, but each export expands to a self-contained JSON Schema.
A builder is not a new normative runtime: **the materialized versioned schema**
and its `$id` remain the sole exported authority. Components with different
nullability, identity meaning or provenance **must not** be unified merely
because their fields share a name.

### Gate before extraction

1. Take exact per-schema Git blob baselines and build a field/definition
   inventory with semantic type, cardinality, optionality, version and
   consumer references. Do not treat identical names as identical semantics.
2. Pilot **two compatible future schema revisions** before designing a global
   framework. Generate byte-for-byte deterministic, self-contained artifacts.
3. Use positive/adversarial fixtures to compare **both accepted and rejected**
   instances against the old validator. Any tighter/looser acceptance is an
   explicit breaking or new-version decision; no silent compatibility claim.
4. Check installed-wheel resource resolution and `ResourceRegistry` paths,
   JSON `$id` uniqueness, source-code imports, Markdown links, and tests
   under the exact HEAD. The package build, frozen root policy and CCG
   v0.1 remain unchanged.
5. Count **total authored lines, generated lines, duplication by validated
   structural identity, edited files, reviewer burden, and new tooling**
   before/after. Reject the framework if these costs rise without a measured
   reduction in drift or maintenance effort.
6. Require a separate approved ADR for any public path, identifier, schema,
   vocabulary, import API, or profile migration. A generated schema still
   needs a stable normative source and provenance.

### One-reference architecture (proposal, not deployed)

```text
immutable source inventory + typed contract-family manifest
    -> field/semantic compatibility audit
    -> reusable primitive definitions (internal only)
    -> deterministic schema composer
    -> self-contained versioned .schema.json artifacts
    -> independent validators + golden positive/negative fixtures
    -> consumer packaging and explicit migration review
```

Avoid storing another copy of all 36 schemas or introducing a new top-level
directory. Reuse `src/codeqa/governance/` for validation and
`tests/` for regression only when the pilot justifies real code. The
current [workflow provenance constraints](workflow-provenance-v0.1.json) and
root layout must not be circumvented by adding workflow files casually.

## Decision D — README diagrams belong to Samuel, not the codeQA evaluator

Issue #282 also requests architecture/concept diagrams in README generation.
Implement as an **opt-in, deterministic, evidence-labelled Mermaid diagram
renderer** in Samuel's read-only `DOCUMENTATION_REFINEMENT` skill, not as a
codeQA quality signal or generated image. Require a caller-supplied graph with
explicit source witnesses; **never infer true architectural relations** from
a diagram's attractive appearance. Prefer GitHub-renderable
`mermaid` fenced blocks, a meaningful textual caption, and preserved
ordinary Markdown title anchors.

**Historical handoff (now completed):** The Mermaid extension was implemented by Samuel PR #248 and adopted by codeQA PR #287 at the exact approved revision. This older design paragraph is not authority to silently repin the central OS in future. Existing README files do not retroactively
become proof of graph correctness.

## Decision status and next actions

| Issue #282 request | Decision now | Actual implementation still needed |
| :-- | :-- | :-- |
| 1. QA vs semantic architecture naming | Distinct reader labels and family responsibility; no breaking file renames | Optional v0.2 public naming migration with alias tests, **separate decision** |
| 2. Schema vs vocabulary | Keep different suffixes because they describe different data kinds | Derivation pilot only if source-of-truth ownership can be proved |
| 3. File count / framework | Measure structural equivalence; two-contract composition pilot with fail-closed parity tests | Pilot implementation and evidence of maintenance improvement |
| 4. Samuel README diagrams | Opt-in evidence-labelled Mermaid renderer | Central skill implementation, test, review and pinned adoption |

**Historical warning, now dispositioned:** Closing #282 does **not** mean all possible public schema renames or a deployed common schema generator shipped. Track accepted follow-on implementation and
review results separately. A successful schema validation or a beautiful
diagram is not a proof of code correctness or a license to rewrite contracts.
