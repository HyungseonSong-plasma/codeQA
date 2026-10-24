# Python override and callback runtime-shape evidence v0.2 draft (#70)

Status: **partial, opt-in, controlled Python only**.

`codeqa.evaluation.python_binding_runtime_v02` uses the *actual in-process*
Python method resolution order (`__mro__`), each class's local dictionary
and `inspect.signature`. A caller must provide explicit positional and
keyword invocation shapes. It distinguishes an absent ancestor declaration,
signature-shape incompatibility, and a merely compatible **candidate**.
A separate function handles framework callbacks; callbacks are not assumed
to be inheritance overrides.

`typing.override` is only a source-intent marker. Neither a syntactic marker
nor successful reflection proves external SDK integrity, type-checker
compatibility, runtime behavior or callback invocation. All returned records
state `sdk_status=NOT_EVALUATED`,
`typechecker_status=NOT_EVALUATED` and
`framework_runtime_status=NOT_EVALUATED`. Compatible observations say
`SIGNATURE_SHAPE_CANDIDATE`, never `TYPECHECKER_VERIFIED_OVERRIDE`.
This module does not execute the callback, run a checker, or rename anything.

Remaining #70 acceptance requires a *pinned external SDK and type/stub
artifact*, an actual pinned type checker/compiler run, overload/protocol
verification, aliased marker provenance, re-exports, metaclass/dynamic
negative controls, trustworthy callback contracts and adversarial SDK drift
tests. Existing Naming v0.1, CCG, Mechanical and QA Result/Delta contracts
are unchanged.
