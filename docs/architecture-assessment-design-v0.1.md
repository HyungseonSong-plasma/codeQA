# Architecture QA design v0.1 — diagnosis before reorganization

**Status:** Proposed (Issue [#165](https://github.com/HyungseonSong-plasma/codeQA/issues/165)); human architecture acceptance pending.  
**Phase:** design-only; no analyzer implementation, source move or compatibility certification.  
**Design fixture:** [architecture scenarios](../fixtures/architecture/design-scenarios-v0.1.json).  
**Feature roadmap:** [#166](https://github.com/HyungseonSong-plasma/codeQA/issues/166), children #167–#174.

## Problem, target outcome and constraints

The codeQA Self Audit exposes function size/call sites and limited domain/import witnesses, but **does not decide** whether the folder tree, Naming placement, Adapter package boundary or language-family grouping is a better design. In particular, the existing [domain inventory](../src/codeqa/evaluation/domain_inventory.py) maps filename hints and source imports; it expressly does not prove semantic cohesion. A `PASS` on the [declared directory role policy](../profiles/semantic-directory-roles-v0.1.json) would mean policy compliance, **not** that the policy or layout is the best choice.

**Target state:** codeQA first diagnoses its own poorly organized areas, supplies comparable evidence and conditional recommendations, then supports a separately approved, safe reorganization and confirms the measured outcome on the same scope. It must also analyze other repositories under their own declared policy rather than assuming codeQA is universally exemplary.

This design preserves the [frozen repository root](repository-structure.md), [adopted package responsibilities](codeqa-package-architecture.md), CCG v0.1, QA Result v0.1, existing Python Mechanical behavior, the Resource Registry and Samuel's exclusive GitHub-mutation ownership. New files remain inside already-allowed root directories; a change to codeQA's **package layout** is a separately governed migration, not a waiver of the root policy.

## Proposed diagnostic implementation ownership

The new evaluator belongs in `codeqa.evaluation.architecture`, not `codeqa.adapters` and not `codeqa.core`. Existing adapters collect language-specific evidence. The Core only carries immutable language-neutral records. Pure evaluation compares a current layout with **virtual** layouts; the pipeline orchestrates these components without reading GitHub or mutating source. Infrastructure retains local Git and resource access only.

```text
src/
  codeqa/
    core/
      architecture.py                 # future immutable scenario/evidence/result DTOs
    adapters/                         # current language evidence collectors (no relocation)
      python.py
      python_dependencies.py          # existing evidence extraction
    evaluation/
      domain_inventory.py             # existing filename/import facts (reuse)
      semantic_layout.py              # existing declared-policy boundary checker (reuse)
      semantic_architecture.py        # existing evidence projection (reuse)
      impact.py                       # existing reverse-dependency candidates (reuse)
      architecture/
        inventory.py                  # proposed folder/package tree + provenance
        metrics.py                    # proposed coverage-bounded import and grouping proxies
        scenarios.py                  # proposed virtual relocation mapping
        migration.py                  # proposed compatibility and move-risk candidates
        assessment.py                 # proposed relative recommendations and missing evidence
    pipeline/
      architecture.py                 # proposed opt-in composition
    governance/                       # existing policy integrity (unchanged)
    infrastructure/                   # existing read-only resource/Git plumbing
contracts/qa/
  architecture-assessment-v0.1.schema.json   # future B7 contract; not shipped by A
profiles/
  architecture-assessment-v0.1.json          # future B7 policy; not shipped by A
fixtures/architecture/
  design-scenarios-v0.1.json                 # A: design manifest, not analyzer output
tests/
  test_architecture_assessment_design.py     # A: design integrity tests
.github/scripts/
  architecture_audit.py                      # future B8 exact-source CI runner
```

Names above are responsibility placeholders, **not an order to create empty Python packages**. B1–B8 will only add files when implemented. The `architecture_audit.py` script is a workflow-owned launcher with input SHA assertions, not the pure pipeline's package owner.

### Dependency direction

```text
External caller/Samuel: repository checkout, selection, immutable identity, mutations
             |
             v
     infrastructure (Git/resource data only)
             |
             v
       pipeline.architecture
          /       |        \
   adapters      core      evaluation.architecture
  (syntax)      (DTOs)      (pure assessment)
      \           ^             /
       \----------+------------/
```

Normative permitted imports remain the current role policy, not this drawing: `core` imports no outer packages; `adapters` may depend on `core`; `evaluation` may depend on `core` but not parser ASTs; `pipeline` composes; `infrastructure` cannot import the other layers; `governance` owns policy integrity. In particular, don't implement a new `evaluation → adapters` exception to get dependency measurements.

### Reuse before adding capabilities

| Existing evidence | What it actually establishes | What B-sub must add |
| --- | --- | --- |
| `domain_inventory.py` and `domain-grouping-v0.1.json` | Filename-hint domains, classified/unclassified coverage, certain static import observations | Directory hierarchy, explicit ownership provenance, coverage beyond recognized Python files (B1/B3) |
| `python_dependencies.py`, `impact.py` | Source-local Python static import candidates and reverse reachability | Scoped proxy metrics with denominators, missing/dynamic consumers (B2) |
| `semantic_layout.py`, `semantic_architecture.py` | Compliance with a declared role model and bounded evidence | Compare the model itself to alternatives without assuming current policy optimal (B4/B7) |
| Adapter capability/source-selection contracts | Declared coverage; some Python execution | Real supported/unsupported language-family readiness, with Rust/C++ unknowns (B6) |
| Self Audit and Domain Inventory CI | Historical/pinned-source reports | Four-question decision report under an exact current checkout (B8) |

## Four required architecture questions and competing hypotheses

The scenario IDs and candidate paths are versioned in the design fixture. No scenario in this document has been measured to be superior.

| ID | Owner's question | Baseline and candidate | Mandatory counterargument |
| --- | --- | --- | --- |
| **L0** | Does the folder layout support the declared responsibilities? | Current `codeqa/{core,adapters,evaluation,pipeline,governance,infrastructure}` | A passing role-rule check cannot establish appropriate ownership or good discoverability |
| **L1** | Should Naming become `codeqa.naming`? | Current dispersed Naming code vs a bounded `src/codeqa/naming` | A filename count does not imply cohesion; moving domain objects can increase Core coupling and imports |
| **L2** | Should adapters sit alongside `codeqa`? | Current `src/codeqa/adapters` vs `src/adapters` sibling package/distribution | A sibling namespace may increase packaging/API burden; external consumer breakage may be unknown |
| **L3** | Should adapters aggregate as `pythonqa`, `rustqa`, `cppqa`? | Flat current adapters vs language-family packages under current or sibling home | Empty future-language directories are not demonstrated scalability; existing Rust/C++ runtime support is incomplete |

After independent evidence, B4 may compose L1+L3 or L1+L2+L3; virtual namespace collisions and package metadata must be checked before scoring. Package proposal L2 is `src/adapters`, **not a new repository root**. An alternate distribution/wheel must be handled explicitly, not assumed by a directory name.

## Evidence and assessment contract (proposed, B7 to formalize)

For each source snapshot and candidate retain:

1. **Identity and coverage:** immutable SHA, selected file set and hashes, analyzer/profile identities, parsed/excluded/unresolved and external-consumer limits; explicitly name unknown files.
2. **Observed tree and imports:** package ownership by path, origin and line for static dependencies, inferred/dynamic resolution limits and public `__init__` candidates; imports alone do not prove runtime links.
3. **Declared authority:** policy role/owner and repository-specific constraints; separate these from observed source facts and provisional hypotheses.
4. **Measurements:** comparable counts and denominators; fan-in/out, SCC cycles, intra/inter group edge ratios, normalized change-surface and cohesion proxies, each marked as a proxy.
5. **Virtual scenario:** bijective original-to-proposed path map; no copy/collision/path escape, no actual source move. Recompute structural metrics with the **same exact original input** and profile.
6. **Migration/compatibility:** explicit rewritten-import candidates, package/build metadata, entry points, registry resources, tests, external users, backwards-compatibility options and unresolved ABI/DSL impact.
7. **Comparison:** evidence per scenario and symmetric comparison with unchanged baselines, sensitivity, trade-offs, assumptions and source witnesses.
8. **Scoped disposition:** `PREFER`, `KEEP`, `REVIEW_REQUIRED` or `INSUFFICIENT_EVIDENCE`; reason and a precise human decision question whenever semantics, public API contracts or compatibility approval is required.

Epistemic classes: `OBSERVED`, `DECLARED_POLICY`, `PROXY_INFERENCE`, `HUMAN_REVIEW`. Neither a compliant directory policy nor more internal imports automatically proves semantic cohesion. Absence of known external callers is **unknown**, not zero. Missing Rust/C++ parser evidence is `NOT_EVALUATED`; the architecture engine cannot manufacture a production adapter. If a critical comparison input differs in scope or is missing, a strong preference is blocked by `INSUFFICIENT_EVIDENCE`, not scored as low risk.

### Mandatory negative controls

- Dynamic import, re-export or runtime plugin target not resolved by static Python imports.
- Unobserved external `codeqa.adapters` consumers after a package move.
- Two functions with similar names but unrelated responsibility; different names with the same responsibility.
- Deliberate shared utility package whose low internal import ratio does **not** prove poor cohesion.
- Alias/namespace collisions, invalid or escaping destination paths, incomplete selected source, inconsistent SHA/profile and unsupported Rust/C++ translation semantics.
- An improved proxy ratio that conceals an increased public migration surface or breaks a known consumer.

## Proof of real cleanup, not just a prettier diagram

A future codeQA-driven cleanup follows an **explicit multi-stage lifecycle**:

```text
Pinned baseline source
  → source-grounded diagnosis + uncertainty
  → compare L0–L3 (+ justified combinations)
  → conditional recommendation + concrete human architecture/API question
  → reviewed, separately authorized migration plan / PR
  → identical-scope analysis + import/API/test/CI gates
  → same-method before/after evidence and resolved/remaining findings
```

A drop in file count, raw import count or a cleaner folder tree alone is not acceptance. Closure must show preservation of existing contracts and a measurable change in ownership/boundary/change-risk evidence, with regression checks and residual unknowns. Evidence of actual maintainability or newcomer comprehension needs independently designed studies; source proxies must not be promoted into such claims.

## Implementation and review gates

1. **A (#165):** adopt/design-review this tree, machine-readable scenario fixture and negative design tests. This phase does **not** implement the analyzer or move production code.
2. **B1–B3 (#167–#169):** inventory, coverage, dependency and Naming ownership evidence. Reuse existing algorithms rather than rename-only refactoring.
3. **B4–B6 (#170–#172):** virtual layouts, migration impact and Python/Rust/C++ family trade-off evaluation, including external unknowns.
4. **B7 (#173):** implement the independent versioned comparative evidence/result contract with fail-closed decision policy and adversarial fixtures.
5. **B8 (#174):** run real codeQA on a pinned codeQA snapshot, produce JSON + readable four-question report with source refs and explicit unknowns. Require actual exact-head CI receipts; a workflow declaration is not execution proof.
6. **Later cleanup (separate migration issue/PR):** never directly reorganize codeQA based only on an unreviewed advisory output. Owner reviews semantics and consumer-compatibility evidence first.

**Human decision at Issue A:** adopt this responsibility boundary and four scenario families as the v0.1 architecture-assessment implementation plan, or request specific changes? This decision does **not** authorize the actual Naming/Adapter migration.
