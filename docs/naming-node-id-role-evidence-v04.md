# #144 Stage 3 — source-grounded node_id role evidence (v0.4, draft)

**Non-adopting scope.** This is a reproducible static-source investigation, not a
semantic Naming PASS or permission to rename anything. The previous Stage 2
audit found 13 declaration/binding sites of `node_id` within 95 pinned Python
files under `src/codeqa`. No actual owner/path role scope has been adopted.

## Distinct grounded source roles

| Static evidence class | Count | Exact rule | What it does not prove |
| --- | ---: | --- | --- |
| Declaration ID generation | 2 | A unique direct `node_id` assignment of a formatted string with literal `def::`, path, lexical name, line and column | Runtime uniqueness across all modules, downstream graph correctness, public API interoperability |
| Typed parameter | 2 | Exact parameter `node_id: str` on the pinned function/method owner/line | That callers use the same identifier encoding, or that renaming is safe |
| Dataclass field candidate | 9 | Exact class-body `node_id: str`, statically verified stdlib dataclass candidate | That every runtime import/consumer uses the same class version or serializer |
 
The selected **internal declaration-node identifier** label is a
`role_candidate` based on local code usage and syntax, not adopted
business/domain semantics. The nine candidate fields are source-level
dataclass field candidates, not universal runtime facts.

## Strong acceptance boundary

The [immutable 13-site witness](../fixtures/naming-governance/codeqa-node-id-role-witness-v04.json)
is versioned independently of
[the full Git scope manifest](../fixtures/naming-governance/codeqa-source-scope-manifest-v04.json).
The opt-in `codeqa.core.naming_node_id_role_evidence_v04.assess_pinned_node_role`
accepts only those thirteen sites in exact order, tied to the independent
95-file pinned AST discovery. For every source involved, it checks a matching
SHA-256 from the independently scanned full source corpus; every structural
rule is rerun on actual immutable source bytes obtained through `GitReader`.
It rejects stale/missing bytes, forged or reordered sites, unsafe f-string
formats, changed parameters, unproved dataclass decorations, guessed roles
and claimed `PASS`/adoption/rename permission. It does not import reviewed
source or execute a project-owned policy DSL.

The checked-in v0.4 semantic candidate policy still contains **zero
approved path-role scopes**, `adoption_status=NOT_ADOPTED`. Local syntax
and generated `def::` identifiers provide stronger source **shape**
evidence than an isolated spelling; they are insufficient to certify
external callers, transitive imports, `node_id` meaning for other
languages, DTO/DB schemas, or compatibility. `semantic_status` remains
`NOT_EVALUATED`; `rename_authorized=false`.

## Scope of this PR and the remaining #144 gates

This is an additive, reviewable evidence mechanism intended for merge
**without** adopting a glossary or changing the frozen Naming v0.1
contracts. A merged implementation is not a green light to close #144.
Remaining work: versioned domain-owner source approvals, precise paths,
semantic FP/FN ground truth, source binding graphs, external SDK/DTO/DB,
mixed-language naming semantics and admissibility under #98/#99.

Regression:
`python -m unittest discover -s tests -p 'test_naming_node_id_role_evidence_v04.py' -v`
