# #91 Naming v0.3 — unsigned review worklist integrity (draft)

**Field-classification boundary:** [Python `declared_field` review contract](naming-field-classification-v03.md) now distinguishes a direct class annotation, a conservative standard-library dataclass field candidate, runtime evidence, and human/policy approval. The classifier is opt-in and does not alter historic #15 `UNRESOLVED`.

**Current human observation checkpoint (2026-10-26):** 4 confirmed, 1 unresolved (#15), 45 unadjudicated. Stage 3–4 counts below are historical; Stage 5 records the attributed amendment and does not adopt the Naming policy.

This is a **mechanical preparation tool** for owner/human review. The merged #117 policy selector and AST observations remain opt-in and do not authorize renaming. The pinned source packet is `fixtures/naming-governance/codeqa-ast-review-v03-proposal.json`: **26 original candidates, 17 additional AST observations, seven negative-control proposals**. Each still lacks a human adjudication. This PR does **not** supply or fabricate one.

## Reviewer workflow

1. Independently retrieve `src/codeqa/core/naming_glossary.py` at pinned commit `dfd94bb25d52642bb2e46766b1ebe074c2f82803`; compare its Git blob `e5da126ead5f25c2eb3be5bb0e16d1c09a430df4` and SHA-256 `09b89f5f492f6d449257e1c6baa4bc1ea98dedd17e93b9f13ced1c62fbcd9d2c`. Do not treat the SHA string inside a submitted worksheet as authentication. The existing #91 AST regression uses a trusted GitReader and recomputes the local Git blob identity.
2. Generate an unsigned worklist from the exact proposal using `build_review_worklist(proposal)`. The 50 deterministic `site_id` values bind the source SHA-256, category, ordinal and exact symbol/line/owner; duplicated spellings at different locations remain distinct.
3. For **each** site, have an accountable human assess source and external applicability. Populate `decision`, `reviewer_login`, a direct evidence URL to a real review comment on Issue #91, and `rationale`. Original and additional observations allow `OBSERVATION_CONFIRMED`, `OBSERVATION_REJECTED`, `UNRESOLVED`; negatives allow `NEGATIVE_CONFIRMED`, `NEGATIVE_REJECTED`, `UNRESOLVED`. A syntactically valid name/comment URL is only a **claim**, not verified provenance.
4. `assess_review_worklist(proposal, submitted)` rejects missing, reordered, duplicated or changed source sites; stale proposal hashes; altered safety flags; missing partial review metadata; and fabricated `PASS`/approval fields. It counts claimed decisions and unresolved cases. **Even 50 completed self-declared claims yield `NOT_EVALUATED`**, never `APPROVED`. Human identity/comment correspondence and review substance must be verified outside this module, and owner must adopt a separately versioned policy.
5. Record separate owner decisions for canonical terms, homonyms, ownership, path/role scopes, exception owner/reason/expiry and the 180-day cadence measured from **actual** adoption. The current proposal keeps path scopes empty, adoption date null and all original signature fields null. `time_step`/`node_id` policy direction is not verified domain semantics; physical-unit suffixes remain lexical only.

## Explicit evidence boundaries

- The 50 sites belong to **one pinned Python file**, not a full repo inventory. False-positive/negative denominators, imports/reexports, dunder/mangling, Unicode/confusables, runtime/dynamic attributes and cross-module aliases need separately sourced specimens and human evaluation.
- This validator checks structural self-consistency, **not** cryptographic human signatures, live GitHub comment ownership, review independence, real external API/DTO/DB compatibility or source-to-deployment equivalence.
- No direct execution of upstream untrusted source, no rename, no Gate PASS, no change to frozen v0.1 default contracts, no policy adoption, no merge permission, and **no Issue #91 closure** is conferred by a worksheet.
- Use the existing #98 Evidence Envelope / #99 Policy Gate for any future externally admissible review evidence. This module does not create a substitute Gate.

## Regression

```sh
python -m unittest discover -s tests -p 'test_naming_review_worklist_v03.py' -v
python -m unittest discover -s tests -p 'test_naming_policy_precedence_v03.py' -v
```

The dedicated `naming-policy-precedence-v03.yml` workflow runs both on changed source/test/worksheet paths. CI success proves structural regression only. The owner must separately review and approve final inventory, negative outcomes and versioned glossary. Until then, this issue remains OPEN.

## Stage 2 — entire pinned source tree and syntactic denominator

`codeqa.pipeline.naming_snapshot_coverage_v03.scan_pinned_git(root, revision=sha40)` enumerates **all Git-tracked Python files under `src/codeqa/` at the exact commit**, reads immutable file bytes through `GitReader`, checks each Git tree blob's independently recomputed Git SHA-1 identity, records each file SHA-256, and refuses missing/unparseable/nonregular/nonportable Python entries. It never uses the current mutable worktree as the source inventory.

The pipeline only reads Git data and composes the pure `codeqa.core.naming_snapshot_coverage_v03` census, respecting codeQA's forbidden core→infrastructure dependency rule. The core module independently traverses Python AST declarations for `function`, `method`, and `parameter` nodes and compares their exact path/line/name/owner/kind multiset against the existing v0.3 declaration observer. This gives an explicit **structural declaration-site denominator** for those three syntax classes, including exact missing/unexpected sites. It is not a denominator for all runtime bindings or eligible Naming rename targets. In particular, class annotations and instance/DTO fields require ownership review, so they are **excluded from this equality denominator**. Reported `uncertainty_categories` count selected AST signs of wildcard/relative imports, dynamic calls, global/nonlocal statements, Unicode/dunder names, fields and import binding without pretending complete detection.

The full-source scan is run in the dedicated workflow using the exact PR raw head SHA (push uses exact commit SHA). Native logs emit the actual selected file and structural site counts. Syntactic match does **not** equal semantic true positive, true negative, false positive, or false negative; all such rates, cross-package reexports, public API/DB compatibility and approved rename safety remain `NOT_EVALUATED` until independent ground truth and an authenticated reviewer are supplied.

```sh
CODEQA_NAMING_PINNED_REV="$(git rev-parse HEAD)" \
  python -m unittest discover -s tests -p 'test_naming_snapshot_coverage_v03.py' -v
```

The new tests reject forged/missing path inventories, changed SHA-256, malformed Python, unsafe paths, semantic PASS claims and verify multi-file identical-name disambiguation. All source reads are local and non-executing. New source census does not alter legacy QA output or the opt-in policy selector.

## Stage 3 — unresolved Batch 1: exact reference candidates and distribution contracts

[Human Batch 1 comment](https://github.com/HyungseonSong-plasma/codeQA/issues/91#issuecomment-6414512106) was posted under GitHub login `HyungseonSong-plasma`. This is **attributed comment provenance**, not proof of independent substantive review or a formal signed Naming-policy adoption. Only #1 and #13 are declared `OBSERVATION_CONFIRMED`; #11, #15 and #25 **remain UNRESOLVED**.

`fixtures/naming-governance/codeqa-batch1-contract-evidence-v03.json` pins those three review-site IDs to the historical source commit/blob/SHA-256 and to their actual review comment. It explicitly preserves `NOT_EVALUATED` external consumer coverage and `NOT_ADOPTED` policy. The fixture is **not** an approved glossary, verified GitHub credential, detached cryptographic signature, or rename permit. Existing `build_review_worklist` is used in regression to reject mismatched IDs and source sites; existing unsigned proposal outcomes are unchanged.

`tests/test_naming_batch1_contract_v03.py` verifies historical Git bytes/blob and AST declaration sites, tests actual tokenizer edge-case outputs, dataclass constructor/frozen/serialization field behavior, valid/invalid `NamingGlossaryProfile.from_mapping` behavior and repeatable fingerprint. When `CODEQA_NAMING_PINNED_REV` is set to a real commit, its source reference test first re-verifies the **entire selected source Git tree** through `scan_pinned_git`, then compares Git-read exact SHA-256 bytes for the evaluator; parses the AST to witness `tokenize_identifier` import and two direct call sites, two `canonical` attribute spellings, and one concrete factory invocation in a tracked test. These are **source-scoped syntactic candidates**, not a fully resolved alias/shadowing graph or proof of all external consumers. The test explicitly distinguishes another class's unrelated `from_mapping`.

The existing `.github/workflows/python-package.yml` now invokes `.github/scripts/naming_batch1_installed_smoke.py` for **both wheel and sdist**, on Python **3.12 and 3.13**, using the repository's isolated venv installation and `python -I` outside the checkout. It checks installed-package location, tokenizer responses/errors, `GlossaryTerm.canonical` constructor/frozen/`asdict` compatibility, and factory/error/fingerprint behavior. Passing tests protect **the observed current package contract**, not downstream SDK/consumer deployments.

### The owner/human follow-up still required

Review #11's public ownership and transitive/dynamic imports; #15's serialized-field/constructor consumers and fingerprint migration; #25's public API, call sites, class-specific homonyms and published wheel clients. Add independently inspected external consumers and verified review evidence where relevant; record per-site dispositions in a later versioned, owner-approved ground-truth packet. Retain all three `UNRESOLVED` until the reviewer explicitly amends #91. Do not equate successful runtime smoke with safe naming rename, policy PASS, or issue closure.

## Stage 4 — scope-restricted human observation adjudication (2026-10-26)

The project owner directed that **external consumers**, **dynamic/transitive reference resolution**, and **API change/rename impact** be explicitly labeled `OUT_OF_SCOPE` for **this limited Batch 1 review**, because those investigations are not feasible now. This is a **scope exclusion, not a favorable result**. It does not satisfy the broader original Issue #91 acceptance items that request independently reviewed public/external aliases, dynamic binding and semantic policy/compatibility. Those remain unmet; do not close #91 on the basis of this scoped review.

The committed evidence packet `fixtures/naming-governance/codeqa-batch1-contract-evidence-v03.json` separates the **review axis** `PINNED_SOURCE_AST_OBSERVATION_ONLY` from the three explicit `OUT_OF_SCOPE` domains. `policy_applicability`, `semantic_equivalence`, `external_impact_safety` remain `NOT_EVALUATED`; `human_policy_adoption` stays `NOT_ADOPTED`, automatic rename and issue closure remain false. The existing Batch 1 GitHub human comment and all three `UNRESOLVED` decisions remain as written until the reviewer posts an **explicit new decision**.

The original human review worklist's `decision` supports `OBSERVATION_CONFIRMED`, `OBSERVATION_REJECTED` or `UNRESOLVED` for the three original candidates, **not** `OUT_OF_SCOPE`. Scope exclusions belong in separate metadata and cannot be submitted as an observation verdict; regression enforces this. If the human reviewer directly verifies the pinned syntax, they can individually confirm:

- **#11 `tokenize_identifier`** — `function` at line 19 with owner `""`; verified Git blob AST `FunctionDef`. External call graph not evaluated.
- **#15 `GlossaryTerm.canonical`** — `declared_field` at line 34, owner `GlossaryTerm`; pinned class-body `AnnAssign`. External constructor/serialization compatibility not evaluated.
- **#25 `NamingGlossaryProfile.from_mapping`** — `method` at line 47, owner `NamingGlossaryProfile`; pinned class-body `FunctionDef` decorated by `@classmethod`. Public SDK compatibility not evaluated.

**Action required of the real human reviewer:** inspect pinned source and explicitly choose `OBSERVATION_CONFIRMED`, `OBSERVATION_REJECTED`, or `UNRESOLVED` *for each* of #11/#15/#25. Post the choices in an attributable new #91 issue comment that cites the historical commit and the existing Batch 1 review. A chat message or code generated by an AI is a proposal, not a signed review; never backfill the outcome without a traceable human comment. All other 45 candidates remain pending independent adjudication.

### Verifiable negative controls

`test_naming_batch1_contract_v03.py` checks exact three excluded domains, strict `OUT_OF_SCOPE` status, retained `NOT_EVALUATED` safety claims, and explicitly rejects using `OUT_OF_SCOPE` as a worklist observation decision. Full source-pinned AST and isolated-wheel runtime tests continue to provide independent evidence within their stated limits.

## Stage 5 — attributed human Batch 1 amendment (2026-10-26)

The actual [owner-posted GitHub amendment](https://github.com/HyungseonSong-plasma/codeQA/issues/91#issuecomment-6415147582) supersedes only the earlier
Batch 1 AST-observation decisions. The original review remains linked at
[Batch 1](https://github.com/HyungseonSong-plasma/codeQA/issues/91#issuecomment-6414512106). Machine-readable `human_amendment` in
`fixtures/naming-governance/codeqa-batch1-contract-evidence-v03.json` records
the observed GitHub author, exact 5 pinned `site_id` values, the per-site
comment URL and a short reviewer-scope rationale. The three previously unresolved
cases now read **#11 CONFIRMED, #15 UNRESOLVED, #25 CONFIRMED**. Original
#1 and #13 remain source-observation CONFIRMED.

The full 50-row review worklist therefore contains **five attributed claims**:
four confirmed, one unresolved; **45 still lack decisions**. The assessment
reports `NOT_EVALUATED` even after these observations are reconciled because
a GitHub comment URL and login do not amount to cryptographically signed,
independently sufficient human policy approval. Tests align each amended
entry to the historical source `site_id`, reject `PASS`/`OUT_OF_SCOPE` as
human observation verdicts, and preserve `policy_adopted=false` and
`automatic_rename_authorized=false`.

The only outstanding Batch 1 observation judgment is whether the annotated
`GlossaryTerm.canonical` at pinned line 34 should be finally classified as
the `declared_field` site proposed in the review inventory. The owner must
independently post `OBSERVATION_CONFIRMED`, `OBSERVATION_REJECTED`, or
`UNRESOLVED`; source syntax alone does not supply that human verdict.

For this limited review, external SDK consumers, dynamic/transitive references,
and API rename compatibility remain explicitly `OUT_OF_SCOPE`. These exclusions
do **not** close the original issue acceptance gates. No auto-rename, official
glossary adoption, semantic PASS, merge approval, or #91 closure is implied.
