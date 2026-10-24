"""#71 controlled opt-in dependency runtime witnesses.

If pinned extras are absent, tests are skipped and MUST NOT count as
framework verification. Run with pydantic==2.13.5 SQLAlchemy==2.0.50.
"""
from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version
import unittest

from codeqa.evaluation.dto_orm_runtime_v02 import (
    RuntimeMappingWitnessError, observe_pydantic_fixture,
    observe_sqlalchemy_fixture,
)


def pinned(package, wanted):
    try:
        return version(package) == wanted
    except PackageNotFoundError:
        return False


@unittest.skipUnless(pinned("pydantic", "2.13.5"),
                     "NOT_EVALUATED: requires pinned Pydantic 2.13.5")
class PydanticEffectiveRuntimeTests(unittest.TestCase):
    def model(self):
        from pydantic import BaseModel, Field, AliasChoices, AliasPath

        class Payload(BaseModel):
            public_id: int = Field(
                validation_alias=AliasChoices("legacyId", "newId"),
                serialization_alias="outboundId")
            nested_value: int = Field(
                validation_alias=AliasPath("payload", "rawValue"))
        return Payload

    def test_actual_inbound_vs_outbound_alias_modes(self):
        Payload = self.model()
        sample = {"legacyId": 5, "payload": {"rawValue": 8}}
        alias = observe_pydantic_fixture(
            Payload, sample, expected_version="2.13.5",
            by_alias=True, trusted_fixture=True)
        original = observe_pydantic_fixture(
            Payload, sample, expected_version="2.13.5",
            by_alias=False, trusted_fixture=True)
        self.assertIn("outboundId", alias.actual_outbound_keys)
        self.assertNotIn("public_id", alias.actual_outbound_keys)
        self.assertIn("public_id", original.actual_outbound_keys)
        self.assertIn("payload", alias.actual_inbound_keys)
        self.assertEqual(alias.public_schema_compatibility, "NOT_EVALUATED")

    def test_output_collision_is_rejected_not_hidden(self):
        from pydantic import BaseModel, Field

        class Collision(BaseModel):
            first: int = Field(serialization_alias="duplicate")
            second: int = Field(serialization_alias="duplicate")

        with self.assertRaisesRegex(RuntimeMappingWitnessError, "collision"):
            observe_pydantic_fixture(
                Collision, {"first": 1, "second": 2},
                expected_version="2.13.5",
                by_alias=True, trusted_fixture=True)

    def test_untrusted_runtime_or_wrong_version_is_blocked(self):
        Payload = self.model()
        sample = {"legacyId": 5, "payload": {"rawValue": 8}}
        with self.assertRaises(RuntimeMappingWitnessError):
            observe_pydantic_fixture(Payload, sample,
                expected_version="2.13.5", by_alias=True)
        with self.assertRaisesRegex(RuntimeMappingWitnessError, "drift"):
            observe_pydantic_fixture(Payload, sample,
                expected_version="0.0.0", by_alias=True, trusted_fixture=True)


@unittest.skipUnless(pinned("SQLAlchemy", "2.0.50"),
                     "NOT_EVALUATED: requires pinned SQLAlchemy 2.0.50")
class SqlAlchemyPhysicalColumnTests(unittest.TestCase):
    def model(self):
        from sqlalchemy import String
        from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

        class Base(DeclarativeBase):
            pass

        class Record(Base):
            __tablename__ = "records"
            id: Mapped[int] = mapped_column(primary_key=True)
            orm_name: Mapped[str] = mapped_column(
                "db_name", String, key="column_key")
        return Record

    def test_mapper_attribute_key_and_physical_name_differ(self):
        witness = observe_sqlalchemy_fixture(
            self.model(), expected_version="2.0.50", trusted_fixture=True)
        member = next(x for x in witness.declared_columns
                      if x.attribute == "orm_name")
        self.assertEqual(member.column_key, "column_key")
        self.assertEqual(member.physical_name, "db_name")
        self.assertEqual(len(witness.ddl_sha256), 64)
        self.assertEqual(witness.database_migration_compatibility,
                         "NOT_EVALUATED")

    def test_db_witness_requires_explicit_trust_and_exact_version(self):
        Model = self.model()
        with self.assertRaises(RuntimeMappingWitnessError):
            observe_sqlalchemy_fixture(Model, expected_version="2.0.50")
        with self.assertRaisesRegex(RuntimeMappingWitnessError, "drift"):
            observe_sqlalchemy_fixture(Model, expected_version="1.0.0",
                                       trusted_fixture=True)


if __name__ == "__main__":
    unittest.main()
