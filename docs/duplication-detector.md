# Source-backed Python duplicate token blocks v0.1 (#38)

This is an **opt-in syntax similarity companion**, not a proof of duplicated
behavior, a P6 quality verdict, or advice to consolidate numerical kernels.
It does not modify existing CCG v0.1, Mechanical P1/P3 or QA Result v0.1.

Input: caller-owned `ParsedSnapshot`, identical source mapping and immutable
`snapshot_id`, plus `duplication_profile`:
`min_block_tokens`, `normalize_identifiers`, `normalize_literals` and
explicit `excluded_prefixes`. Exclusions for generated/vendor/templates are
policy data, not repository-name heuristics. Profiles have SHA-256 canonical
fingerprints; extraction and evaluation must agree exactly.

Algorithm: tokenize each selected, successfully parsed `.py` once (comments
and formatting whitespace are excluded). Select complete, body-only function
and method blocks; skip enclosing functions with nested function/class
scopes, to prevent counting nested code twice. Each eligible block gets
source relative path, lexical node identity, start/end lines, token count and
SHA-256 of the optionally normalized token sequence (token types included).
Exact matching fingerprints form deterministic duplicate groups. There is
**no near-duplicate or semantic-clone detection** in v0.1.

`evaluated_tokens` is the total token count of eligible nonoverlapping
function bodies. `duplicate_excess_tokens` counts copies beyond the first
block in each exact-match group, and
`observed_duplicate_fraction=duplicate_excess_tokens/evaluated_tokens`,
with unit **fraction of eligible tokens**. This denominator deliberately
excludes small blocks, unsupported files, explicitly excluded generated
source and nested scopes. A null fraction and `NOT_EVALUATED` mean no
eligible observations; they are never transformed to clean PASS.

Status is `OBSERVED_DUPLICATION`, `NO_DUPLICATES_OBSERVED` or
`NOT_EVALUATED`; `unprocessed` and `not_evaluated` reasons remain
visible even alongside observed groups. No source is imported/executed and
no clones outside the supplied input are asserted. Canonical report schema
`contracts/qa/duplication-report-v0.1.schema.json` and opt-in API
`extract_python_token_blocks` / `evaluate_duplication` are independent
of the immutable QA Result v0.1. #40 may consume versioned evidence only
through explicit compatibility checks.

Conformance: `tests/test_duplication.py` covers literal/identifier
normalization, same basenames in distinct paths, partial parse, minimum
block size, nested exclusion, generated/vendor exclusions, profile drift,
token witnesses, input-order determinism and legacy result stability.
