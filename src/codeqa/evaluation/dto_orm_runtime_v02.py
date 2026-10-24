"""Controlled, opt-in DTO/ORM mapping observations (#71).

This intentionally executes *trusted synthetic fixture* model code. Never
invoke it during AST-only analysis or on arbitrary untrusted application code.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from importlib.metadata import PackageNotFoundError, version
from typing import Any


class RuntimeMappingWitnessError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class PydanticMappingWitness:
    dependency_version: str
    model_identity: str
    declared_field_aliases: tuple[tuple[str, str, str, str], ...]
    actual_inbound_keys: tuple[str, ...]
    actual_outbound_keys: tuple[str, ...]
    by_alias: bool
    runtime_status: str = "CONTROLLED_SYNTHETIC_RUNTIME_OBSERVED"
    public_schema_compatibility: str = "NOT_EVALUATED"
    production_runtime_status: str = "NOT_EVALUATED"


@dataclass(frozen=True, slots=True)
class OrmColumnWitness:
    attribute: str
    column_key: str
    physical_name: str


@dataclass(frozen=True, slots=True)
class SqlAlchemyMappingWitness:
    dependency_version: str
    mapped_identity: str
    declared_columns: tuple[OrmColumnWitness, ...]
    ddl_sha256: str
    runtime_status: str = "CONTROLLED_SYNTHETIC_METADATA_OBSERVED"
    database_migration_compatibility: str = "NOT_EVALUATED"
    production_database_status: str = "NOT_EVALUATED"


def _require_version(package: str, expected: str) -> str:
    if not isinstance(expected, str) or not expected:
        raise RuntimeMappingWitnessError("exact dependency version must be declared")
    try:
        actual = version(package)
    except PackageNotFoundError as exc:
        raise RuntimeMappingWitnessError("optional dependency unavailable") from exc
    if actual != expected:
        raise RuntimeMappingWitnessError("dependency version drift")
    return actual


def observe_pydantic_fixture(
    model: Any, inbound: dict[str, Any], *,
    expected_version: str, by_alias: bool, trusted_fixture: bool = False,
) -> PydanticMappingWitness:
    if not trusted_fixture:
        raise RuntimeMappingWitnessError("runtime fixture execution needs explicit trust")
    if not isinstance(inbound, dict) or not isinstance(by_alias, bool):
        raise RuntimeMappingWitnessError("explicit input and by_alias mode required")
    actual = _require_version("pydantic", expected_version)
    try:
        import pydantic
        if not isinstance(model, type) or not issubclass(model, pydantic.BaseModel):
            raise RuntimeMappingWitnessError("Pydantic BaseModel type required")
        populated = model.model_validate(inbound)
        emitted = populated.model_dump(by_alias=by_alias)
    except (ImportError, AttributeError, TypeError) as exc:
        raise RuntimeMappingWitnessError("unsupported Pydantic runtime evidence") from exc
    if not isinstance(emitted, dict) or not all(isinstance(k, str) for k in emitted):
        raise RuntimeMappingWitnessError("non-string serializer field keys")
    field_aliases = []
    output_names = []
    for key, field in model.model_fields.items():
        emitted_name = (field.serialization_alias or field.alias or key) if by_alias else key
        output_names.append(emitted_name)
    if hasattr(model, "model_computed_fields"):
        for key, computed in model.model_computed_fields.items():
            emitted_name = (computed.alias or key) if by_alias else key
            output_names.append(emitted_name)
    if len(output_names) != len(set(output_names)):
        raise RuntimeMappingWitnessError("effective output alias collision")
    for key, field in model.model_fields.items():
        field_aliases.append((
            key, repr(field.alias), repr(field.validation_alias),
            repr(field.serialization_alias),
        ))
    return PydanticMappingWitness(
        actual, model.__module__ + "." + model.__qualname__,
        tuple(sorted(field_aliases)), tuple(sorted(inbound)),
        tuple(sorted(emitted)), by_alias)


def observe_sqlalchemy_fixture(
    model: Any, *, expected_version: str, trusted_fixture: bool = False,
) -> SqlAlchemyMappingWitness:
    if not trusted_fixture:
        raise RuntimeMappingWitnessError("SQLAlchemy fixture requires explicit trust")
    actual = _require_version("SQLAlchemy", expected_version)
    try:
        from sqlalchemy import inspect
        from sqlalchemy.dialects import sqlite
        from sqlalchemy.schema import CreateTable
        mapper = inspect(model)
        table = mapper.local_table
        columns = []
        for attribute in mapper.column_attrs:
            for column in attribute.columns:
                columns.append(OrmColumnWitness(
                    attribute.key, str(column.key), str(column.name)))
        ddl = str(CreateTable(table).compile(dialect=sqlite.dialect()))
    except (ImportError, AttributeError, TypeError, ValueError) as exc:
        raise RuntimeMappingWitnessError("unsupported SQLAlchemy mapping evidence") from exc
    if not columns:
        raise RuntimeMappingWitnessError("no controlled mapped SQL columns")
    return SqlAlchemyMappingWitness(
        actual, model.__module__ + "." + model.__qualname__,
        tuple(sorted(columns, key=lambda x: (x.attribute, x.column_key))),
        sha256(ddl.encode("utf-8")).hexdigest())
