# Issue #91 — deterministic source-only closure criteria

**Revised scope; the original Issue #91's semantic acceptance is not represented as completed.** The bounded work concerns **50 exact historical sites in one pinned Python source file**, not an entire repository semantic naming proof.

## Normative source rules
1. Resolve the historical Git commit and byte-for-byte source identity (Git blob SHA-1 and SHA-256). Derive the 50 original `site_id` values from the same proposal; no reindexing or synthetic human signatures.
2. For ordinary AST symbols, match source name, kind, line and lexical owner exactly. For decorators require expression syntax only, and treat `__future__` as directive syntax rather than renameable import binding.
3. For seven legacy `declared_field` sites, use the static dataclass classifier and accept the **bounded** `DATACLASS_FIELD_CANDIDATE` outcome, not runtime `FIELD_CONFIRMED`.
4. Seven negative controls require unique exact source-site matches. Each is `NEGATIVE_CONTROL_RENAME_EXCLUDED`: automatic rename disallowed; no assertion that the name is semantically incorrect.
5. All ambiguity, missing declarations, forged bytes or mismatched scope must yield `UNKNOWN` / `BLOCKED_UNKNOWN` or raise. A single unknown blocks scoped acceptance.
6. No automatic rename, domain synonym/homonym inference, SDK/DTO/DB compatibility, complete import graph, or official semantic glossary adoption from the AST result.

## Machine closure gate
- 50/50 sites classified, exactly zero unknown, seven field candidates, seven negative controls; identity and grouping exact.
- Adversarial tests reject stale bytes, fabricated statuses/approval, reordered/missing records and acceptance inflation.
- Pure AST core and independent Git-provenance pipeline agree, do not execute reviewed source.
- Frozen Naming v0.1 and existing review records unchanged.
- Exact PR HEAD checks all success, protected-branch merge is verified.
- **Before #91 closes**, a separate *open* successor issue must explicitly retain the original semantic glossary, mixed-language, external API, policy-adoption and reviewer-level obligations. This transfer means **outstanding**, not satisfied. The explicit open successor is [#144](https://github.com/HyungseonSong-plasma/codeQA/issues/144).

Schema: `fixtures/naming-governance/codeqa-rule-acceptance-v03.json`.
`closure_gate=PASS` refers only to this constrained source-AST rule review.
The historical human #15 verdict can remain `UNRESOLVED` without blocking a separately scoped deterministic source classification; it is **not** retroactively rewritten as a human approval.
