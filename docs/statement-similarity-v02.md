# Repeated direct function-statement patterns v0.2 (#53)

The opt-in Python direct-body statement detector addresses a known blind spot:
whole-function token-duplicate v0.1 cannot discover repeated *complex
statements inside the same function*. Its API/schema and QA Result/Delta
contracts remain unchanged.

## Scope and evidence

- `extract_python_statement_patterns(parsed, sources, snapshot_id=...,profile=...)`
  is a Python Adapter. It parses no new source and never imports/executes
  inspected code. The caller supplies an immutable source snapshot identity,
  UTF-8 source text, a cached ParsedSnapshot and a profile.
- Only complex statements **directly in a declared function/method body**
  (`if`, `for`, `while`, `try`, `with`, `match`) are considered.
  Nested, async and class methods keep distinct lexical owner identities.
  Statements nested inside branches or loops are **not** recursively mined
  as standalone pattern candidates. This is an explicit v0.2 coverage
  boundary, not evidence of absence of deeper repetition.
- Token count from the actual source segment enforces a configurable
  minimum (18 by default). Normalization is explicit: identifier spelling
  and primitive literal contents may be replaced with typed placeholders.
  AST operators, attribute spelling and control-flow shapes remain
  significant. All grouping happens **within the same function owner**.
- Each candidate has a source-relative path, unique lexical function owner,
  exact start/end lines, actual source-file SHA-256, token count and
  normalized AST SHA-256. Profile SHA-256 is rechecked against extraction.
  Generated/vendor path exclusions are profile-owned and reported.
- Results expose `eligible_direct_statements` as the **denominator**,
  repeated statement occurrences, concrete groups and parse/exclusion
  limitations. There is no invented duplicated-code percentage, automatic
  extraction requirement or behavioral-clone claim.

The pure evaluator `evaluate_statement_similarity` only consumes the
language-neutral `StatementPatternEvidence` model from Core. It checks
hashes, bounds, producer identity, source scopes, duplicate positions and
policy drift. Output conforms to
`contracts/qa/statement-similarity-v0.2.schema.json`.

## Frozen MOOSE empirical reproduction

Pinned source fixtures for original, Blind and Guided
`physics_harness/analysis/field_comparison.py` come from #48's
independently Git-blob-verified commit inventory:

| Arm | Repeated tolerance validation guard pattern |
| --- | --- |
| Base | Two near-identical `if` guards at lines **20** and **22** → observed |
| Blind | Guards consolidated into one helper → **not observed as repeated** |
| Guided | Both near-identical guards remain → observed |

The source-only detector identifies AST-syntax similarity. It does **not**
prove the two guards are equivalent in all contexts, that a helper is
always appropriate, or that Blind has generally better architecture.

Tests in `tests/test_statement_similarity.py` cover the real three-arm
snapshots; identifier/literal normalization toggles; min size;
different comparison operators; whitespace/comments; nesting; generated
source exclusion; syntax errors and unsupported extensions; stale cached
source digests; evidence/profile tampering; v0.1 immutability and
deterministic output. CI checks the frozen source bytes independently.

This closes one **detection-scope gap** but does not supply a blanket P6
cohesion verdict, automatic DRY recommendation or full Python expression
equivalence.
