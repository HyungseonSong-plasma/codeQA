# Issue #144 — source-bound lexical semantic candidates (v0.4 draft)

**Status: NOT_ADOPTED.** This is a deterministic, opt-in precondition for a future
semantic glossary. It is **not** an official Naming glossary, policy PASS, runtime
field proof, or source rename mechanism. It does not replace the generic #98
Evidence Envelope or #99 Policy Gate.

## Input and evaluation boundary

- **Source witness:** caller supplies exact UTF-8 Python bytes, selected path,
  SHA-256, symbol name/kind/line/lexical owner. The evaluator recomputes SHA-256
  and requires an exact AST declaration, not text in comments, strings or other
  scopes. Independent Git commit provenance is an orchestration responsibility;
  hash equality alone does not authenticate a Git snapshot.
- **Fields:** a class-body `AnnAssign(simple=1)` is insufficient by itself.
  The existing standard-library dataclass classifier must also return
  `FIELD_CANDIDATE`; this remains short of runtime field certification.
- **Glossary:** only explicit lowercase ASCII canonical terms and aliases.
  No inferred synonyms/homonyms, CamelCase transformations, physical-unit
  conversions, DTO semantic roles, reexports, runtime alias resolution or
  external SDK compatibility. Whole underscore-delimited token sequences must
  match; simultaneous term matches become `UNKNOWN`.
- **Scopes:** explicit path prefix, Python kind and role are mandatory.
  Longest segment-aligned path prefix wins. Missing, conflicting, unrecognized
  or inapplicable scopes cannot produce a positive candidate.
- **Negative controls:** explicit excluded spellings such as `dt` and
  `timestamp` are negative **inference** controls only; exclusion is not a
  finding that a real domain identifier is semantically wrong.
- **Authority:** `LEXICAL_RULE_MATCH_CANDIDATE` always retains
  `semantic_proven=False` and `rename_authorized=False`. No GitHub comment,
  human review signature or official glossary adoption is invented here.

## Machine-readable outcomes

| Outcome | Meaning |
| --- | --- |
| `LEXICAL_RULE_MATCH_CANDIDATE` | Exact source AST, explicit term and declared role scope agree; semantic meaning not verified |
| `EXCLUDED` | Exact AST observed; explicit negative-inference spelling blocks a candidate |
| `UNKNOWN` | Missing AST site or scope, role mismatch, ambiguous terms, unsupported spelling, unresolved field or untested external consumer |
| Exception | Malformed policy, token collision, duplicate equal-precedence scopes, source digest drift or unparseable source |

The checked-in fixture deliberately has `scopes: []`, and every term has
`meaning_status=PENDING_DOMAIN_EVIDENCE`. The fixture therefore yields **no
approved semantic matches**, even when the historical AST declaration exists.
The spelling pairs `time_step`/`timestep` and `node_id`/`nodeid`, and
excluded inferred synonyms, reproduce the existing #91 owner-direction
proposal without adopting it. The `runtime` and `data` labels are unapproved
illustrative roles pending separate scope/ownership decisions. Positive scoped
cases in the tests are **synthetic demonstrations**, not official naming
policy evidence.

## Residual work under #144

Official source/domain glossary ownership and meaning evidence; exact owner
and path scopes; real import/reexport/dynamic reference graphs; consumer-bound
SDK/DTO/DB compatibility; mixed-language inventories; field/alias false-
positive and false-negative denominators; exception expiration; and typed
external admission through #98/#99 remain **NOT_EVALUATED**. Any successor must
fail closed on ambiguity and not promote lexical candidates into semantic
PASS or automatic rename.

Regression: `python -m unittest discover -s tests -p 'test_naming_semantic_candidate_v04.py' -v`.

## Stage 2 — actual pinned source scope discovery

[Read-only 95-file pinned Git scope audit](naming-scope-discovery-v04.md) now checks the entire selected `src/codeqa/**/*.py` corpus from `main@667a5f17f9890c5588d4f1c8ae079aba241501f3`, selects only actual AST sites for the four owner-proposed spellings, and retains `role=UNKNOWN` for every site. No approved `scopes` are added and the audit does not yield a semantic PASS.
