# Non-mutating Rename Impact v0.2 draft (#76)

**Status:** proposal-only candidate evidence; *not accepted as a migration plan*.
This is an additive draft interface. All frozen CCG, Naming v0.1,
Mechanical and QA Result/Delta contracts remain unchanged.

## Scope

`codeqa.evaluation.naming_rename_impact_v02.assess_rename_impact` consumes:
an exact pinned `git:owner/repo@sha40` source revision, selected UTF-8
sources with SHA-256 evidence, a typed declaration with line witness,
caller-supplied reference witnesses, an exact policy ID, and a proposed name.

The standalone `contracts/qa/naming-rename-impact-v0.2-draft.schema.json`
validates the report. There is **no source editor, file write or patcher**.

## Boundary and evidence limitations

The caller supplies boundary classes independently; this evaluator does not
resolve them from source text. `public_api`, `external_sdk`, `override`,
`dto_inbound`, `dto_outbound`, `db_physical`, `rust_trait`,
`cpp_virtual_abi` and `moose_reserved_dsl` always require contract review.
Unresolved dynamic calls, generated code, unknown boundaries and incomplete
source selection remain unknowns. Lexical witnesses only establish token
occurrence on a pinned line; they **do not** establish binding, executable
behavior, interface compatibility or a rename's safety.

Even an apparently internal rename produces `UNVERIFIED_PROPOSAL`, never
`SAFE_TO_RENAME`. The `migration_plan` field is always
`HUMAN_REVIEW_REQUIRED`. Actual AST binding provenance, external consumer
verification, migration sequence and rollback obligations are future work
and cannot be inferred from a few fixtures or passing tests.

## Required human review for completion

A reviewer must supply an approved migration plan and regression scope,
sign off on public/SDK/DTO/SQL/Rust/C++/MOOSE boundary evidence, and approve
the source-scope, policy and reference completeness. An approved plan is a
separate document and does **not** authorize automated source rewriting.
