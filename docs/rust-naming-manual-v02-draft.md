# Rust manual naming witnesses v0.2 draft (#72)

**Selected implementation mode:** `manual_curated_fixture` (explicitly
not parser-backed). This opt-in draft is a human-readable fixture contract,
not a production Rust source parser.

The versioned policy in `profiles/rust-naming-manual-v0.2-draft.json`
declares per-kind conventions. The pinned fixture SHA-256 and 15 manual
witnesses under `fixtures/rust-naming/` are verified against exact source
lines, but neither the evaluator nor those witnesses prove a repository Git
revision or Rust AST producer. The profile and report explicitly state
`parser_status=NOT_EVALUATED`, `compiler_status=NOT_EVALUATED`,
`trait_resolution_status=NOT_EVALUATED` and
`source_revision_status=NOT_EVALUATED`.

Unverified `impl Trait` methods take precedence over local project style:
`processInput` is NOT_EVALUATED, not a requested rename. Inherent helper
`BadHelper` may be a STYLE_REVIEW_CANDIDATE. Macros, expanded tokens,
external re-exports, raw identifiers and generated names are intentionally
NOT_EVALUATED. The evaluator does not bind traits, expand macros, run rustc,
invoke cargo, rewrite source, guarantee Unicode collision safety or certify
runtime behavior.

This is an incremental, separate-language Naming witness facility. Existing
Python adapters, frozen Naming v0.1, CCG, Mechanical and QA Result/Delta
contracts remain unchanged. Full #72 acceptance still requires reviewer
confirmation of this mode and project override policy, a source-grounded
production/real pinned witness suite, adversarial trait/library compatibility
evidence and optionally version-pinned compiler conformance. A green CI for
the synthetic fixture alone cannot close the issue.
