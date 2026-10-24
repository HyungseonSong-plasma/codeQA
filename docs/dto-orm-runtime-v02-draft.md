# Controlled DTO / ORM runtime observations v0.2 draft (#71)

Status: **opt-in synthetic runtime experiment**, not a public API or DB
migration certification. The original v0.1 directional Naming report and
frozen CCG/Mechanical/QA Result/Delta contracts remain unchanged.

The evaluator `codeqa.evaluation.dto_orm_runtime_v02` is deliberately
separate from the static AST analyzer. It **executes a trusted Pydantic
model** only when `trusted_fixture=True` and the installed dependency
is exactly Pydantic `2.13.5`. It records declared
`alias`, `validation_alias`, `serialization_alias` metadata, actual
accepted input keys for the supplied sample, and emitted keys under an
explicit `by_alias` mode. Effective output-name collisions fail closed.

The SQLAlchemy witness requires version `2.0.50`, inspects controlled
mapped classes to distinguish the Python ORM attribute, `Column.key`
and physical database column `Column.name`, and records a SQLite DDL
SHA-256. It **does not** connect to a production DB, apply migrations,
validate third-party consumers or prove schema compatibility.

To run dependency-backed opt-in tests:

```bash
python -m pip install 'pydantic==2.13.5' 'SQLAlchemy==2.0.50'
python -m unittest tests.test_dto_orm_runtime_v02 -v
```

The default codeQA CI does not install these optional dependencies.
A skipped test must be reported as NOT_EVALUATED, not evidence of runtime
framework compatibility. Full acceptance still requires separately
versioned public schema comparisons and compatibility windows, inherited
and reflected SQLAlchemy columns, computed/omitted output fields, controlled
schema drift, malicious/dynamic negative fixtures, and a reviewed migration
plan. User-supplied models may execute validators; do not run against
untrusted arbitrary source.
