# Naming #91: Python `declared_field` boundaries (opt-in v0.3 draft)

**Status: DRAFT / NOT_ADOPTED.** Existing `declared_field` output and the 50 historical worklist site identities remain unchanged. This contract narrows what can be independently proven before human adjudication. No automatic rename, Naming policy PASS, or Issue #91 closure.

## Three distinct propositions

1. **Source observation:** at an immutable Git blob/SHA-256, a unique top-level Python class contains a direct `ast.AnnAssign` whose simple target is the exact `Name`, line and owner. This is an annotated class-scope name, not proof of an instance/dataclass field. Parenthesized targets have `simple=0`; `self.x`, subscripts, method-local and conditional annotations are not the same site type.
2. **Static standard-library dataclass candidate:** `FIELD_CANDIDATE` requires a uniquely resolved and prior direct stdlib `@dataclass` import, exactly one decorator, no inheritance/metaclass, a direct simple annotated name, supported builtin type spelling, no known shadowing/redefinition/dynamic class body/default evaluation, and no proven pseudo-field. This is a conservative *source* predicate, not runtime field certification. `ClassVar`, `InitVar`, `KW_ONLY` are pseudo-fields when marker provenance is statically resolved. Uncertain markers or qualifiers go to `REVIEW_REQUIRED`. Ordinary classes yield `CLASS_ANNOTATION_ONLY`.
3. **Runtime dataclass field:** requires separate, versioned trusted witness linking actual loaded class/source/package to `dataclasses.is_dataclass(cls)` and membership in `dataclasses.fields(cls)`. Runtime introspection or installed API checks may establish current behavior; they cannot certify all external consumers or safe rename. Inherited-vs-declared site, constructor parameters, `asdict`/serialization, descriptors, defaults, fingerprints, API and DTO/DB consumers require their own evidence.

## Investigated gaps and dispositions

| Counterexample / risk | Disposition |
| --- | --- |
| Plain `class C: x: int` | `CLASS_ANNOTATION_ONLY`, not an instance-field proof |
| `ClassVar[T]`, `InitVar[T]`, `KW_ONLY` with resolved stdlib imports | `PSEUDO_FIELD_EXCLUDED`; **not** `declared_field` |
| `Final[T]` | Do **not** equate with `ClassVar`; require review (Python dataclasses can include it as a field) |
| Alias imports, shadowing, type aliases, string annotations, duplicate bindings | `REVIEW_REQUIRED` without proven identity |
| `(x): T`, `obj.x: T`, `x[0]: T`, method-local `self.x` | No positive simple direct class-name certificate |
| Extra/custom decorators, dataclass_transform, Pydantic, attrs, delayed imports | `REVIEW_REQUIRED`; different semantic owners |
| Inherited/overridden definitions, metaclasses, property/descriptor defaults | `REVIEW_REQUIRED`; source role does not establish runtime field provenance |
| Class-body `exec`, conditional mutation, `__annotations__` rewriting, duplicate declarations | `REVIEW_REQUIRED`; execution-dependent namespace |
| `field(init=False)`, kw-only/generated constructors, slots, frozen | Field identity and constructor/slot/mutation properties are **separate** assertions |
| Dynamic bindings, external SDK/DTO/DB, serialization keys, fingerprint changes | Outside limited Batch 1 source review, **not** a successful compatibility verdict |

Reference: [Python 3.13 AST AnnAssign](https://docs.python.org/3.13/library/ast.html), [standard dataclasses and pseudo-fields](https://docs.python.org/3.13/library/dataclasses.html), [typing dataclass_transform](https://typing.python.org/en/latest/spec/dataclasses.html). The narrow classifier in `src/codeqa/core/naming_field_classification_v03.py` has adversarial regression tests in `tests/test_naming_field_classification_v03.py`. It never executes or imports untrusted target bytes and returns a constant `runtime_field_verification=NOT_EVALUATED`, `naming_policy_applicability=NOT_EVALUATED`, `rename_authorized=false`.

## Historical `GlossaryTerm.canonical` (Issue #91 row #15)

At pinned commit `dfd94bb25d52642bb2e46766b1ebe074c2f82803`, `src/codeqa/core/naming_glossary.py`, line 34, the name `canonical` is a direct class-body `AnnAssign(simple=1)` of type `str`; `GlossaryTerm` is decorated by a syntactically resolved stdlib `@dataclass(frozen=True,slots=True)`. The narrow static classification is `FIELD_CANDIDATE`, **not** `FIELD_CONFIRMED`. A separate runtime regression checks it is present in `dataclasses.fields(GlossaryTerm)` for the current test installation, not for external consumers.

The original review kind `declared_field` remains a **proposed human inventory classification**, with `UNRESOLVED` as the latest attributable owner decision. The user must explicitly decide whether to accept that historically pinned AST/field role; this document does not impersonate or replace human review.

**Future migration gate:** any promotion of legacy `declared_field` to a normative taxonomy requires an independently versioned schema, field-kind denominator, source-to-runtime evidence coverage, explicit exclusions/UNKNOWN, consumer compatibility review, and separately approved policy ownership. Preserve frozen Naming v0.1 and existing worklist identities until then.

## Additive v0.3 shadow projection of the original 50-site worklist

The opt-in `codeqa.core.naming_field_evidence_v03.build_shadow_field_evidence`
creates a **new and separately versioned** packet (`0.3-shadow-field-evidence`)
without changing the 50 legacy IDs, the source proposal, the declared kind
`declared_field`, or any review decision. The pure core accepts exact source
bytes; `codeqa.pipeline.naming_field_evidence_v03.project_pinned_field_evidence`
reads them via `GitReader` from the proposal's immutable commit.

The packet is restricted to `original_candidates` already labeled
`declared_field` (seven entries in the historical worklist). Every record
preserves its `site_id`, precise `symbol` identity and `legacy_kind`;
adds `ast_site`, `static_classification` and `reason_codes`; and explicitly
marks runtime verification, human decision import, policy applicability and
rename authorization as **not granted**. All other 43 worklist records stay
unaltered and are not silently classified. `FIELD_CANDIDATE` is a static
candidate, never `FIELD_CONFIRMED`.

`validate_shadow_field_evidence` recalculates this projection from exact
source and proposal and rejects missing, extra, reordered, forged, stale
or approval-promoting fields. Tests check unchanged 50-site identities,
historical Git SHA-1 blob and SHA-256, seven original field candidates,
the owner-comment #15 `UNRESOLVED`, and both negative and spoofed
evidence. Underlying source SHA/blob validation alone does not independently
verify Git identity; the pipeline's immutable Git read provides that provenance.

**Migration stage:** `ADDITIVE_SHADOW_ONLY`. No replacement of the legacy
public AST kind, no default-policy change, no overall field denominator
for the 91+ Python files, no runtime claim from the static sidecar, and no
human or glossary approval. Any normative schema/kind migration remains a
separate governed decision after broader counterexample, compatibility
and semantic coverage review. Source/field classifications remain provisional.

Run:
```sh
python -m unittest discover -s tests -p 'test_naming_field_evidence_v03.py' -v
```

## Bounded no-review closure gate

[Deterministic source-rule acceptance](naming-rule-acceptance-v03.md) evaluates the exact 50 historical source sites without turning their syntax into domain/glossary approval or modifying prior human decisions. Previous Issue #91 semantic obligations must be preserved in a separate open successor, never silently marked satisfied.
