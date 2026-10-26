# Issue #144 — pinned actual-source scope discovery (v0.4 candidate)

**Status: evidence exploration only; `NOT_ADOPTED`.** This expands Draft PR #145 with a read-only audit of *actual* tracked Python source files at the immutable codeQA `main` snapshot `667a5f17f9890c5588d4f1c8ae079aba241501f3`. No path scope, business/domain owner, semantic term meaning, official glossary, or automatic rename authority is created.

## Coverage and provenance

- `fixtures/naming-governance/codeqa-source-scope-manifest-v04.json` pins the Git commit and root tree SHA plus the **95 exact Git-tracked Python source paths under `src/codeqa`** and their Git blob SHA-1 identities. These are the **selection denominator**, not inferred from current working-tree files. The manifest excludes tests/docs, dynamic/imported modules and outside-repo consumers.
- `codeqa.pipeline.naming_scope_discovery_v04.discover_pinned_semantic_scope` independently re-enumerates the exact `git ls-tree` for the pinned commit, verifies *complete path identity* and every listed blob ID, then reads every immutable source file through `GitReader`. It checks each byte stream's reconstructed Git blob SHA-1, computes a SHA-256, and parses all 95 sources. Missing, extra, substituted, unparseable, or stale paths fail closed. A successful run warrants **only** the selected pinned-tree corpus.
- `codeqa.core.naming_scope_discovery_v04.scan_explicit_spellings` uses AST declarations rather than substring matches. It selects the four explicit owner-proposed spellings `time_step`, `timestep`, `node_id`, `nodeid`, separating functions, methods, parameters, class annotations, assignments, imports, and unresolved attribute/name references. Method/class ownership is *lexical*, not runtime.
- `proposed_path_role_scopes` can include only **actually observed** declaration sites. Their roles remain `UNKNOWN` and `approved_scope=false`. No rule generator can infer `physics`, `runtime`, `data`, DTO orientation, unit equivalence, or that lexical names are interchangeable in downstream use.

## Evidence-to-policy boundary

The existing `codeqa-semantic-candidate-v04.json` fixture retains `scopes=[]`,
`NOT_ADOPTED`, and `PENDING_DOMAIN_EVIDENCE`. An AST declaration found in a
real file would justify *investigating* that exact path/kind/owner, **not**
automatically adding it to the official glossary. If none of the four
target spellings occur in pinned source declarations, the resulting zero
candidates is a legitimate negative *within this selected corpus*; it
does **not** establish an absence across repository tests, external SDK,
runtime dynamic imports, strings/configuration, or other languages.

Any observed `attribute_unresolved`, `import_alias` or
`name_reference_unresolved` is **not** a completed binding graph.
The scanner deliberately does not enumerate every Python expression
(e.g., function decorator/default expressions, all import-star effects);
therefore `source_reference_completeness=NOT_EVALUATED` regardless of count.
`semantic_policy_gate=UNKNOWN` and `automatic_rename_authorized=false`
remain mandatory even when the selected pinned-tree parsing gate passes.

## Adversarial regression and next gate

`tests/test_naming_scope_discovery_v04.py` checks the immutable 95-file
selection denominator, Git blob checks, 100% selected-source parse,
source/role/term mutation rejection, exact AST ownership, class annotations
versus actual dataclass fields, unresolved attributes and lexical negative
controls. The dedicated Naming workflow runs it on each relevant PR.

**Remaining Issue #144 acceptance:** ownership and scope decisions grounded
in actual domain requirements; selected real-source positive/negative
semantic ground truth; import/reexport transitive alias graph and callers;
external SDK/DTO/DB compatibility; Unicode, mixed-language coverage and
versioned policy adoption through #98/#99. None is inferred from this audit.

## Verified path/owner source candidates (Stage 2 checkpoint)

The [versioned 13-site fixture](../fixtures/naming-governance/codeqa-real-source-role-sites-v04.json) is bound to the Git tree and the full 95-file scan. It records **13 distinct AST declaration/binding candidates, all spelled `node_id`**, with exact file, line, and lexical owner; **nine** are `class_annotation`, **two** are `parameter`, and **two** are `local_binding`. The other three target spellings have **zero structural declaration candidates in this selected source corpus**. The scan also records syntactic references separately: presence is not declaration or compatibility evidence.

A `class_annotation` is intentionally **not** asserted to be a runtime field, especially if its declaration lacks validated dataclass or descriptor semantics. `local_binding` is **not an approved Naming field**. For every row, `role=UNKNOWN` and `approved_scope=false`. The checked-in policy still has `scopes=[]`, and the joined real-source `_stable_symbol(node_id)` parameter is tested to return `UNKNOWN:NO_EXPLICIT_ROLE_SCOPE` from `SemanticCandidateRules`.

The fixture is a reproducible baseline for future owner-domain meaning assessment, *not* a policy configuration and not a validated symbol/binding graph. If source changes, a new pinned commit, complete path denominator and separately reviewed candidate fixture are required; none of these rows authorize rename.

## Stage 3 — real code evidence by source role

The [13-site source-grounded `node_id` witness](naming-node-id-role-evidence-v04.md) now verifies two `def::` identifier generators, two string parameters and nine standard-library dataclass string-field candidates against exact pinned source AST and the complete Stage 2 Git tree audit. This justifies a **lexical source-role candidate**, not an approved path/role scope or semantic Naming policy. The original owner glossary proposal remains `NOT_ADOPTED`, and source rename is prohibited.
