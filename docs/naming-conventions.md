# Python Naming Convention safe-baseline MVP (Issue #61, Phase 1)

**Status:** Opt-in, source-only declaration-style companion, not a project-wide
quality score or automatic renamer. The full cross-language glossary, class
hierarchy and verified external SDK/DTO mapping ambitions in Issue #61 remain
separate capabilities. Frozen CCG v0.1, Mechanical v0.1 and QA Result/Delta
contracts are unchanged.

## Inputs and codeQA layer ownership

- Caller provides repository-selected UTF-8 Python source, caller-owned
  `ParsedSnapshot`, immutable snapshot ID and versioned profile.
- Python Adapter `extract_python_naming(parsed, sources, snapshot_id=...)`
  extracts declarations, AST import aliases, direct local base member names,
  decorator spelling, annotated DTO field and literal serializer/DB aliases.
  **Source is not imported or executed.** It checks cached AST SHA-256.
- Core contains immutable `NamingEvidence`, `NamingSymbol`,
  `NamingProfile` and declared contract records.
- Pure Evaluation `evaluate_naming(evidence, sources, profile)` validates
  immutable source selection/checksums, producer/version, policy and lexical
  findings. No repository I/O or Python Adapter dependencies in Evaluation.
- Use resources `python_naming_safe_profile` and
  `naming_report_schema`. The default profile's static name styles are
  module/function/method/parameter/field/import alias `snake_case` and
  class `PascalCase`. Explicit vendor/generated prefixes are exclusions.
  Profile fingerprint preserves effective policy identity.

Example:

~~~python
from pathlib import Path
from codeqa.infrastructure.resources import ResourceRegistry
from codeqa.adapters.python_snapshot import parse_python_snapshot
from codeqa.adapters.python_naming import extract_python_naming
from codeqa.core.naming import NamingProfile
from codeqa.evaluation.naming import evaluate_naming

registry = ResourceRegistry(Path("."))
profile = NamingProfile.from_mapping(
    registry.load_json("python_naming_safe_profile")
)
sources = {"src/example.py": "class Adapter:\n    def run_task(self): pass\n"}
parsed = parse_python_snapshot(sources)
evidence = extract_python_naming(
    parsed, sources, snapshot_id="git:owner/repo@" + "a"*40
)
report = evaluate_naming(evidence, sources, profile)
print(report.to_document())
~~~

An explicit `snapshot_id` is a **caller attestation**, not proof codeQA
fetched the corresponding Git bytes. CI independently pins a real codeQA
source file in `fixtures/naming-codeqa` by its SHA-1 Git blob digest.

## Binding safeguards (before style)

| Syntax / evidence | Handling |
| --- | --- |
| Source-grounded matching member of unique local ancestor class | `EXEMPT_BY_INTERFACE_CONTRACT`, exact ancestral spelling protected |
| `@typing.override` / aliased `@typing_extensions.override` but local ancestor lacks method | `REVIEW_REQUIRED` for **override intent mismatch**, not mere case |
| External/unresolved base, ambiguous multiple inheritance | `NOT_EVALUATED` for potential override; no speculative rename |
| Imported original member `from vendor import OddAPI` | `EXEMPT_BY_POLICY`; original third-party spelling protected |
| Explicit local import alias `OddAPI as odd_api` | Independently checked under local import-alias style |
| Exact pinned external contract supplied by caller | `EXEMPT_BY_DECLARED_CONTRACT`, explicitly **attested, not runtime-verified** |
| Pydantic `Field(validation_alias=..., serialization_alias=...)` | Literal syntax recorded. **Only internal Python field spelling** is checked; effective output behavior not proven |
| SQLAlchemy `mapped_column("USER_ID")` | DB column spelling is separate from Python field style; no DDL proof |
| Direct Pydantic field / computed alias / unresolved mapper | `NOT_EVALUATED` for potential external binding |
| Ordinary non-protected local declaration | Applied naming case rule, including narrow private/dunder exceptions |

**Important known limitations:**
The adapter's local inheritance classifier handles direct resolvable
same-file class ancestry; it does not resolve Python's dynamic MRO,
monkeypatching, external package implementations, overload compatibility
or actual runtime dispatch. `@override` is intent, not runtime proof.
Pydantic/SQLAlchemy recognized import spellings are source-only evidence,
not a proven serializer configuration. Literal mappings cannot certify
external API or database schema compatibility. Inferred terms, glossary
synonyms, Java/Rust/C++/MOOSE DSL semantics, end-to-end references and
automatic rename candidates are deliberately absent. Unsupported
constructs must be treated as outside MVP coverage.

## Findings and interpretation

- `CONFORMANT_WITH_APPLIED_RULE`: declaration spelling meets **one** selected rule.
- `REVIEW_REQUIRED`: witnessed local style mismatch or evidenced
  locally invalid `@override` intent (separate reason).
- `EXEMPT_BY_POLICY` / `EXEMPT_BY_INTERFACE_CONTRACT` /
  `EXEMPT_BY_DECLARED_CONTRACT`: source-grounded, scoped protection,
  with declared contracts separately marked as attested.
- `NOT_EVALUATED`: external/DTO ancestry or alias binding incomplete;
  never a clean naming pass.

Coverage counts and parser failures are explicit. A top-level
`NO_VIOLATIONS_OBSERVED` result is **not** a global project-quality
certification and is conditioned on the selected source set.
External contracts require exact path, owner, field/member spelling,
provider, revision and rationale. Duplicate IDs are invalid.

## Acceptance and future work

`tests/test_naming_safe.py` covers private/dunder style, verified local
override vs sibling, invalid override intent, unresolved external bases,
aliased external imports, exact external contract attestation, literal and
dynamic DTO mapping, DB-column casing, partial parse, stale AST/source
hashes, exclusions, Unicode and profile drift. A pinned codeQA source
fixture is SHA-verified; CI independently compares it with the immutable
original commit and executes the test suite. A follow-up PR is required
for hierarchy resolution beyond the same file and framework-specific
effective serializer/ORM mapping, a cross-language convention catalog,
glossaries and renaming migrations. Do not close the entire #61 roadmap
based solely on this MVP.
