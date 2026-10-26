# #144 Stage 4 — exact-source import witnesses and scope-admission boundary

**Status: additive engineering evidence; official Naming glossary NOT_ADOPTED.**
This stage defines machine-checkable minimum conditions for recognizing a
*source-role scope candidate*, and explicitly blocks premature external
compatibility or semantic-policy approval.

## Pinned real-source check

At immutable `codeQA@0177958aeb82ecdb019655244e35aef97e9e0fea`,
`ControlFlowObservation.node_id` is an annotated `str` field candidate
of the standard-library dataclass in `src/codeqa/core/complexity.py:10`.
Two **selected** internal consumers directly import that **class symbol**:

- `src/codeqa/adapters/python_complexity.py:12`
- `src/codeqa/evaluation/complexity.py:8`

The opt-in `naming_import_scope_gate_v04` requires exact Git blob
identities for all **three** selected files, the declared owner/field/line,
the dataclass static classifier's `FIELD_CANDIDATE`, and one exact
top-level `from codeqa.core.complexity import ControlFlowObservation`
in each client. The imported class name must have a lexical AST load.
No target source is executed or imported by the checker.

This is a **selected consumer denominator of 2**, not all possible
internal callers, not a complete import graph, and not proof that
`node_id` attribute accesses bind to that class. The result
`DIRECT_IMPORT_SYNTAX_WITNESSED` certifies a source import *statement*,
not a runtime binding identity or transitive reexport.

## Fail-closed behavior

The classification returns `UNKNOWN` for missing/duplicate imports,
aliased imports, wildcard or relative imports, obvious rebinding,
dynamic namespace operations and conditional module-body structures.
Malformed data or any drift in pin, file, owner, import line, or
unapproved authorizing fields raises `ImportScopeEvidenceError`.
Adversarial regression includes a synthetic direct-import positive
example and independent negative examples.

A direct import is **not** evidence that no other module reexports the
class or that external clients have been audited. Reexport, dynamic/
transitive alias graph and broad binding completeness therefore remain
`NOT_EVALUATED`. The absent external-source bundle is explicitly
`external_client_evidence=NOT_SUPPLIED`; consequently
`external_api_compatibility=UNKNOWN`.

## Policy admission distinction

`source_role_scope=SOURCE_SHAPE_ADMISSIBLE_ONLY` means *these exact*
source shapes may be considered by a future role owner. It does **not**
approve `path_prefix` or role assignments in
`codeqa-semantic-candidate-v04.json`; `scopes=[]` remains unchanged.
No domain owner or canonical meaning was inferred, no source renamed.
`semantic_policy_gate=UNKNOWN`, `glossary_policy=NOT_ADOPTED`,
`owner_approval=NOT_ADOPTED`, and `rename_authorized=false`.

For eventual semantic admission, the future governed policy must
independently substantiate meaning and role ownership, complete
import/reexport binding resolution, actual SDK/DTO/DB call sites and
compatibility, and mixed-language semantic FP/FN ground truth, with
evidence admission under #98/#99. An opt-in static-source witness does
not substitute for those requirements.

Regression:
`python -m unittest discover -s tests -p 'test_naming_import_scope_gate_v04.py' -v`
