# Semantic Architecture Ontology v0.1

This is a small, source-evidenced architectural ontology: NOT RDF/OWL, a runtime solver or a complete P1–P8 evaluator.

## Separation of concerns

- CCG v0.1: immutable declarations, CCG edges and conservative local target resolutions.
- EvidenceIndex: source locations and deterministic evidence IDs.
- Semantic Ontology: role and responsibility declarations, source-file containment, code entities, import observations, evidence and forbidden dependency constraints.
- Assessment: the existing semantic directory-role policy evaluator remains the authority for explicit forbidden edges and exact transitional exceptions.

## Contracts and boundaries

- Versioned vocabulary: `contracts/semantic/architecture-v0.1.vocabulary.json`.
- JSON Schema: `contracts/semantic/architecture-v0.1.schema.json`.
- Language-neutral model: `src/codeqa/core/semantic_architecture.py`.
- Pure projector: `src/codeqa/evaluation/semantic_architecture.py`.
- Repository-specific roles: `profiles/semantic-directory-roles-v0.1.json` or a supplied external policy.

`owns_responsibility`, `prohibited_dependency` and constraint endpoints express POLICY_DECLARATION. They are **normative**, not observed behavior. Source containment and code-entity membership follow analyzed paths. `imports` is STATIC_MODULE_PATH evidence, NOT a runtime dependency. Only already CCG-resolved `calls`/`defines` can be projected as such; the projector never promotes unresolved targets. An Import observation receives a `supported_by` edge only if a unique source-line AST witness exists. Same-line multiple Import statements remain without a guessed witness.

## Outcome semantics

VIOLATION: explicit forbidden role edge or missing declared role with complete coverage. REVIEW_REQUIRED: named transitional exception or stale exception. NOT_EVALUATED: unclassified roles, incomplete coverage or unsupported assertions. The overall outcome is **never PASS/ALIGNED** merely because no forbidden syntax was observed. Unmapped imports remain uncertainty, not negative evidence. Function names and directory names are NOT automatically classified as behavior.

The following dimensions are explicitly unassessed in v0.1: behavior versus responsibility, runtime dependency semantics, library/DSL semantics, scientific domain contracts and test relevance. Future semantic predicates require an explicit, versioned ground-truth source and adversarial tests.

## Usage

```python
analysis = analyze_python(
    pinned_sources, snapshot_id=pinned_source_sha,
    ccg_schema=ccg_schema, mechanical_profile=mechanical_profile,
    semantic_policy=declared_directory_role_policy,
)
print(analysis.semantic_architecture.summary_document())
```

The optional `semantic_policy` leaves old CCG, Mechanical, Dependencies, Evidence, Symbol Calls, and Contextual Review unaffected when omitted. Frozen root layout and CCG v0.1 remain unchanged.

## Retrospective MOOSE adapter

The fixed moose-test-repo external audit applies a deliberately partial
codeQA-compatible role policy at
`profiles/moose-test-directory-roles-subset-v0.1.json`.
Its provenance is the later Physics policy source commit recorded in the
profile. It declares all fifteen current roles but imports **only rules that
forbid an entire role**, never broadening `adapters.moose` to all `adapters`.
Historical analyzed code and later ownership-policy dates are explicitly
different. The resulting projection is RETROSPECTIVE and NOT proof that
the old source met the architecture policy at its original date.
Narrow subsystem constraints, subprocess behavior and approved operational
exceptions remain solely with the native moose Architecture Guard.
