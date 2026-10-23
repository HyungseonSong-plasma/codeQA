# Directional DTO / DB mapping source evidence — #64

**Opt-in companion.** A field's Python identifier, accepted input alias,
emitted output alias and physical database column are **four distinct names**.
The existing Naming v0.1 findings are unchanged.

`extract_python_directional_fields(parsed, sources, contract_source,
snapshot_id=..., profile=...)` accepts caller-selected source bytes,
an already parsed snapshot and an exact pinned JSON external-schema text.
The schema must match the declared provider/revision and SHA-256 in
`profiles/python-directional-fields-v0.1.json`; each selected field has
an exact path/class/name/schema-model binding. No network/imports or
user-code execution.

The Python AST Adapter handles only qualified static `pydantic.Field`
with literal `alias`/`validation_alias`/`serialization_alias`
and `sqlalchemy.orm.mapped_column("DB_COLUMN")`.
`validation_alias` overrides `alias` for inbound reads, and
`serialization_alias` overrides `alias` for outbound writes.
This describes only **declared alias syntax**, NOT the effective serializer
(e.g. Pydantic `by_alias`, config, custom field serializers or ORM
reflection). Any missing/dynamic alias or unknown mapping remains
`NOT_EVALUATED` for the affected direction.

The language-neutral Evidence and a pure Evaluator produce per-direction:
- `DECLARED_MATCH_NOT_RUNTIME_VERIFIED` for literal source syntax
  equal to the exact pinned external schema key.
- `DECLARED_MISMATCH` if observed literal aliases differ.
- `ALIAS_COLLISION` for multiple fields claiming one directional
  external alias in the same model.
- `NOT_EVALUATED` for unobserved/unsupported direction.
No automatic renaming or mutation, no inference of 1:1 mapping, and
never a universal API or database compatibility PASS.

The frozen `fixtures/naming-dto/field-contract.json` is a **synthetic**
source-identity test, not a claim an actual third-party service was checked.
`tests/test_naming_fields.py` exercises alias direction, literal SQL
column casing, import aliases, source shadowing, dynamic input keys, schema
digest/revision drift, missing fields and fabricated evidence.
Use the registered resources `python_directional_fields_profile` and
`directional_fields_report_schema`.

Follow-up needed for actual Pydantic runtime configuration/serializer
paths, SQLAlchemy DDL verification, nested/flattened mappings, versioned
migration policy and cross-language APIs. Existing CCG/QA Result/Delta
contracts remain unchanged.
