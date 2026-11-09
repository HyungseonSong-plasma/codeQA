# Naming glossary governance v0.2 draft (#74)

Status: **AWAITING_HUMAN_REVIEW**, additive and opt-in. This does not replace
the already accepted v0.1 lexical glossary or certify semantic correctness.

`codeqa.core.naming_glossary_governance_v02` parses an explicit repository
policy containing owned canonical tokens, enumerated aliases, expiration dates,
permitted declared roles and versioned path/language/identifier-category
scopes. The policy parser rejects alias ambiguity, circular aliases, duplicate
equal-precedence scopes, unsafe source paths and non-ASCII canonical spellings.
The most specific matching path wins. A result is one of
`ROLE_NAME_MATCH_CANDIDATE`, `ROLE_NAME_REVIEW_CANDIDATE` or `NOT_EVALUATED`.
No result is a semantic PASS. No identifier or source is rewritten.

Unit suffix names (e.g. `_ms`, `_s`) are only lexical tokens and **never**
prove dimensional equivalence, physical correctness or valid conversion.
External SDK/API names are explicitly excluded from local rename decisions.
The deliberate lexical-only behavior also means this draft does not establish
cross-module symbol identity, homonym disambiguation or mixed-language intent.

A separate fixture under `fixtures/naming-governance/` cites seven negative
control candidates from exact codeQA commit
`dfd94bb25d52642bb2e46766b1ebe074c2f82803`; tests verify Git blob
identity, SHA-256 and AST line witnesses. Every human outcome remains null.
These candidates are **not** a human-reviewed ground truth inventory.
The future reviewer must approve/reject each candidate, official term
ownership and expiration, and any architecture-to-terminology mapping before
this issue may be closed.

Tests are additive; existing frozen CCG, Mechanical, Naming v0.1 and QA
Result/Delta schemas are untouched.
