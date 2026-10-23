# ADR 0004 — Versioned naming convention contracts and scope of completion

**Status:** Accepted, 2026-10-23. **Owner:** codeQA Foundation, design issue
[#61](https://github.com/HyungseonSong-plasma/codeQA/issues/61).
**Decision scope:** opt-in, source-grounded Naming Convention architecture;
Python baseline and bounded companions; independent future language support.

## Context

Naming conventions differ by language, project, framework and public
interface. Applying one casing heuristic to all identifiers can break
`@override` methods, vendor imports, serialized DTO fields, physical
database columns and MOOSE input reserved words. Conversely, exempting
all subclasses or data transfer objects conceals ordinary local style
violations. Static syntax is evidence of spelling, not proof of runtime
binding, semantic responsibility or external compatibility.

The original [design issue #61](https://github.com/HyungseonSong-plasma/codeQA/issues/61)
also accumulated future implementation requirements. Completing its
**design** must not be misrepresented as delivering Rust/C++/MOOSE
production adapters, runtime serializer or type-checker verification,
source-scope Naming Delta, or an automatic rename engine.

## Accepted decision

1. **Repository policy as data, opt-in.** Provide a standard, explicitly
   selected language profile with independent repository/path/kind rules,
   exact documented exclusions and versioned policy fingerprints. Do not
   impose a cross-project universal naming style. Conflicting policy
   applicability requires review or rejection, not arbitrary precedence.
   The current [Python default profile](../../profiles/python-naming-safe-v0.1.json)
   is an implemented *baseline*, not a complete policy hierarchy.
2. **Preserve architecture boundaries.** Caller owns immutable source
   selection/revision identity and any pinned external evidence; language
   Adapters extract source facts without executing inspected code; Core
   carries language-neutral immutable evidence; Evaluation performs
   conservative policy judgments; report schemas and registry resources
   are independently versioned. See
   [architecture](../architecture.md) and
   [original Naming design](../naming-conventions.md).
3. **Interface contract before local style.** A uniquely evidenced
   inherited method name or declared external extension point is
   protected narrowly. `@override` alone is intent, not a proven
   Python override. Imported original names are not renamed; a locally
   chosen alias is governed separately where safely known. An external,
   dynamically constructed or ambiguous inheritance relationship stays
   `NOT_EVALUATED` and is never silently treated as conformant.
   [Pinned ancestor declarations](../naming-external-ancestor.md)
   strengthen static evidence but do **not** establish runtime MRO or
   compatible signatures.
4. **Internal vs external field identities are distinct.** Evaluate
   internal declarations, accepted input key(s), emitted output key and
   database physical column under separate direction/namespace policies.
   Exact alias syntax plus a pinned contract can establish a *declared*
   match; effective serializer config, write-time options, ORM reflection
   and upstream API compatibility need separate evidence.
   [Directional mapping](../naming-directional-fields.md) reports
   `DECLARED_MATCH_NOT_RUNTIME_VERIFIED`, not a certified interface.
5. **Terminology is explicitly declared.** A project owns canonical
   tokens and alias/abbreviation policies. Evaluate source token spelling
   with fixed scope; do not infer semantic equivalence, runtime units,
   behavioral cohesion or synonymy from string similarity. See
   [project glossary](../naming-glossary.md).
6. **Uncertainty is a first-class outcome.** Every measured or exempt
   declaration carries a policy identity, original location, source
   provenance and basis. Unsupported categories, partial parses,
   ambiguous imports, shadowing, incomplete external mappings and
   unobserved references are visibly limited/`NOT_EVALUATED`. A lack of
   observed violations is neither a whole-repo naming certification nor
   a guarantee that renaming is safe.
7. **Compatibility and non-mutation.** Maintain independently versioned
   opt-in naming companions; do not silently mutate CCG v0.1,
   Mechanical v0.1, QA Result/Delta v0.1 or strict Delta v0.2. The
   analyzer emits observations/review candidates, not patches. An
   automatic source rename is explicitly **not part of this ADR**.

## Shipped, bounded source evidence

| Adopted component | Implemented artifact | Scope and limitation |
| --- | --- | --- |
| Python Naming safe baseline | [profile](../../profiles/python-naming-safe-v0.1.json), [schema](../../contracts/qa/naming-report-v0.1.schema.json), [tests](../../tests/test_naming_safe.py); [PR #62](https://github.com/HyungseonSong-plasma/codeQA/pull/62) | AST declarations, original imports, local ancestry and conservative DTO symbols. Not complete Python semantic resolution |
| Pinned external ancestor name matching | [profile](../../profiles/python-pinned-ancestor-v0.1.json), [tests](../../tests/test_naming_ancestor.py); [PR #66](https://github.com/HyungseonSong-plasma/codeQA/pull/66) | Pinned *direct declarations*, not type-checked runtime overrides |
| Directional DTO/DB aliases | [profile](../../profiles/python-directional-fields-v0.1.json), [tests](../../tests/test_naming_fields.py); [PR #67](https://github.com/HyungseonSong-plasma/codeQA/pull/67) | Statically declared aliases against pinned synthetic schema; not effective runtime or DDL verification |
| Declared lexical glossary | [profile](../../profiles/python-naming-glossary-v0.1.json), [tests](../../tests/test_naming_glossary.py); [PR #68](https://github.com/HyungseonSong-plasma/codeQA/pull/68) | Exact caller-declared tokens/aliases only; no semantic inference |

These are separate `[tool.codeqa.resources]` entries in
[pyproject.toml](../../pyproject.toml), with distinct report schema IDs.
Their regression checks passing demonstrates only the documented
behavioral boundary and tests, not completeness of the larger roadmap.

## Transfer of the original incomplete acceptance conditions

The open checkboxes in issue #61 are **historical unfulfilled
implementation requirements**, not tasks falsely marked complete.
They are deliberately transferred, with independent closure criteria,
to these follow-ups:

| Follow-up | Remaining acceptance category |
| --- | --- |
| [#69](https://github.com/HyungseonSong-plasma/codeQA/issues/69) | Python declaration and policy coverage, exceptions, false-positive inventory and actual evidence-review gate |
| [#70](https://github.com/HyungseonSong-plasma/codeQA/issues/70) | Verified type-checker/compiler external overrides, signatures, inherited public interfaces and callbacks |
| [#71](https://github.com/HyungseonSong-plasma/codeQA/issues/71) | Effective directional serializer/ORM behavior, external schema and DB migration compatibility |
| [#72](https://github.com/HyungseonSong-plasma/codeQA/issues/72) | Rust naming declarations, trait and macro capability |
| [#73](https://github.com/HyungseonSong-plasma/codeQA/issues/73) | C++ naming, compiler-backed overrides, MOOSE reserved DSL and framework API names |
| [#74](https://github.com/HyungseonSong-plasma/codeQA/issues/74) | Repository glossary governance and explicit domain/architectural role-name alignment |
| [#75](https://github.com/HyungseonSong-plasma/codeQA/issues/75) | Comparable source-scope Naming Delta across pinned revisions |
| [#76](https://github.com/HyungseonSong-plasma/codeQA/issues/76) | Non-mutating rename impact assessment, API/ABI/DSL migrations and human approval |

The implemented subissues [#63](https://github.com/HyungseonSong-plasma/codeQA/issues/63),
[#64](https://github.com/HyungseonSong-plasma/codeQA/issues/64)
and [#65](https://github.com/HyungseonSong-plasma/codeQA/issues/65)
are closed independently. Future implementations require their own
positive/adversarial conformance, source-scoped policy and reviewable
version/contract changes, never a blanket PASS from this ADR.

## Completion criterion and consequences

**Issue #61 closes when this ADR and scope-transfer record are merged
with green exact-head and postmerge CI.** This closure means
`Naming architecture / contract design accepted`, **not**
`all naming analysis capabilities shipped`. In particular, #69–#76
remain actionable and may not be treated as completed by #61's closure.

**Verification:** [Naming tests](../../tests/test_naming_safe.py),
[pinned ancestor](../../tests/test_naming_ancestor.py),
[directional fields](../../tests/test_naming_fields.py),
[glossary](../../tests/test_naming_glossary.py) and
[architecture documentation gate](../../tests/test_architecture_contract_docs.py).
These verify documented invariants within the selected evidence scopes
and do not imply vendor runtime compatibility.
