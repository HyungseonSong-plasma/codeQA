# #91 Naming v0.3 — unsigned review worklist integrity (draft)

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
