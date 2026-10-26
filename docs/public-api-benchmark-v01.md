# #92 — Public API/DB benchmark v0.1 (source-only)

**Approved benchmark:** `fastapi/full-stack-fastapi-template` at immutable
commit `b1125d8839482cb7bbae603ddc6d0081bf87532e`, tree
`94de969c70c4d283e7a57eb0795cea9a8d7813ef`. Upstream license:
MIT. Selected backend project version: `0.1.0`; Python requirement
`>=3.14,<4.0`. This is a source snapshot, **not** a versioned public
deployment/compatibility window.

The machine-readable inventory
`fixtures/python-sdk/public-api-benchmark-v0.1.json` records **11**
independently read Git blob SHA-1 identities and byte-level SHA-256 digests:
MIT license, dependency manifest, actual SQLModel/Pydantic models, FastAPI
users routes, **all five** Alembic revision sources and both generated
TypeScript consumer files. The source-only runner
`.github/scripts/public_api_benchmark.py` downloads these exact pinned
bytes read-only from GitHub, independently verifies Git object hashing,
SHA-256 and the pinned upstream Git tree, and rejects unexpected/missing
migration files. Upstream application Python, migration code, npm and
install scripts are **never executed**.

The selected **named consumer is TypeScript**:
`frontend/src/client/types.gen.ts` and `sdk.gen.ts` (generated
`UsersService`). It is **not** a Python SDK. The checker uses Python
AST and source-only TypeScript declaration extraction to compare the
selected `UserPublic`, `UserCreate`, `UserRegister`, `UsersPublic`,
`ItemPublic` and `UserUpdateMe` field names and required/optional
status, named FastAPI `response_model` bindings, and selected generated
SDK methods. Unexpected static field aliases and dynamic model configuration
fail closed for this limited benchmark. This is **not** a complete TS
typechecker or generator/serializer equivalence proof.

The checker reconstructs the five-revision Alembic predecessor chain,
compares initial physical `user`/`item` column names against source
`sa.Column` declarations and current SQLModel table field names, and
identifies the intermediate **data-dependent integer-to-UUID migration**
with `uuid_generate_v4()` and `new_owner_id`. The chain is source-bound,
but **no PostgreSQL, Alembic migration, data backfill, actual database,
API server, frontend application, or generated OpenAPI runtime is executed**.
The historical integer→UUID transition may be incompatible for external
consumers; migration correctness and backwards-compatibility are
`NOT_EVALUATED`, not `PASS`.

The CI runner also executes eight deliberate negative controls:
forged source bytes, missing selected consumer, missing migration tree edge,
mismatched DTO consumer field, wrong route response model, unreviewed
serialization alias, broken migration predecessor and altered physical
column. A negative test passing means the scoped checker rejected the
tampering; it is not a general correctness proof. Receipts are stored as
`public-api-benchmark.json` inside the existing pinned Python SDK
artifact. A fetch/network failure is a CI failure, never a compatibility
PASS.

**Remaining independent work:** a separately pinned real typed **Python**
SDK and named consumer/typechecker witness (overload, mixin, metaclass,
re-export, aliased decorator, callback/override), actual public
compatibility version windows, generator provenance, dynamic alias and
callback dispatch semantics, PostgreSQL data-dependent migrations, and
independent human review. The existing controlled Pydantic 2.13.5 /
SQLAlchemy 2.0.50 / Pyright 1.1.414 tests are preserved and are not
relabelled as production conformance. All PRs remain Draft; #92 OPEN.
