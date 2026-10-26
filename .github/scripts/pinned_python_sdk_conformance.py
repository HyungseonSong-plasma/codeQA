#!/usr/bin/env python3
"""Issue #92: real pinned Pyright + Pydantic + SQLAlchemy controlled conformance.

Never executes user-provided source; does not certify production APIs/migrations.
Pyright findings are parsed from real JSON, not simulated.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
from importlib import metadata
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from codeqa.core.external_evidence import ToolIdentity, assess_external_evidence, parse_external_evidence
from codeqa.evaluation.evidence_gate import EvidenceRun, evaluate_gate, parse_gate_policy
from codeqa.infrastructure.resources import ResourceRegistry

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "fixtures/python-sdk"
PIN = {"Pydantic": "2.13.5", "SQLAlchemy": "2.0.50", "pyright": "1.1.414"}
CHECKED_RULE = "reportIncompatibleMethodOverride"


def digest(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def need(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def _attested_diagnostic_file(
    issue: object, project: Path, *, extra_source: Path | None,
) -> str:
    """Map a real Pyright diagnostic to an exact scanned file, never its basename."""
    need(isinstance(issue, dict), "PYRIGHT_MALFORMED_DIAGNOSTIC")
    raw_path = issue.get("file")
    need(isinstance(raw_path, str) and bool(raw_path),
         "PYRIGHT_DIAGNOSTIC_SOURCE_MISSING")
    source = Path(raw_path)
    actual = (source if source.is_absolute() else project / source).resolve()
    permitted = {"contract.py": (project / "contract.py").resolve()}
    if extra_source is not None:
        permitted["public_sdk.py"] = (project / "public_sdk.py").resolve()
    matched = [name for name, expected in permitted.items() if actual == expected]
    need(len(matched) == 1, "PYRIGHT_DIAGNOSTIC_OUTSIDE_ATTESTED_SOURCE")
    return matched[0]


def _validate_pyright_diagnostics(
    parsed: dict, project: Path, *, extra_source: Path | None,
) -> list[dict]:
    """Fail closed on truncated or misattributed JSON before constructing evidence."""
    summary = parsed["summary"]
    count = summary.get("errorCount")
    need(type(count) is int and count >= 0, "PYRIGHT_INVALID_ERROR_COUNT")
    analyzed = summary.get("filesAnalyzed")
    need(type(analyzed) is int and analyzed >= (2 if extra_source else 1),
         "PYRIGHT_INCOMPLETE_SCAN_COUNT")
    diagnostics = parsed["generalDiagnostics"]
    for issue in diagnostics:
        file_name = _attested_diagnostic_file(
            issue, project, extra_source=extra_source)
        need(issue.get("severity") in ("error", "warning", "information"),
             "PYRIGHT_UNKNOWN_DIAGNOSTIC_SEVERITY")
        rule = issue.get("rule")
        need(rule is None or (isinstance(rule, str) and bool(rule)),
             "PYRIGHT_MALFORMED_DIAGNOSTIC_RULE")
        span = issue.get("range")
        need(isinstance(span, dict) and isinstance(span.get("start"), dict),
             "PYRIGHT_MALFORMED_DIAGNOSTIC_RANGE")
        line = span["start"].get("line")
        need(type(line) is int and line >= 0,
             "PYRIGHT_MALFORMED_DIAGNOSTIC_LINE")
        source_lines = (project / file_name).read_text(encoding="utf-8").splitlines()
        need(line < len(source_lines), "PYRIGHT_DIAGNOSTIC_LINE_OUTSIDE_SOURCE")
    errors = [issue for issue in diagnostics if issue["severity"] == "error"]
    need(count == len(errors), "PYRIGHT_ERROR_COUNT_MISMATCH")
    return errors


def check_versions() -> dict[str, str]:
    reported = {}
    for name in ("Pydantic", "SQLAlchemy"):
        expected = PIN[name]
        found = metadata.version(name)
        need(found == expected, f"WRONG_VERSION {name}: wanted {expected}, got {found}")
        dist = metadata.distribution(name)
        metadata_bytes = dist.read_text("METADATA")
        need(metadata_bytes is not None, f"missing wheel metadata: {name}")
        reported[name] = digest(metadata_bytes.encode("utf-8"))
    package = ROOT / "node_modules/pyright/package.json"
    need(package.is_file(), "PYRIGHT_PACKAGE_MANIFEST_MISSING")
    manifest = json.loads(package.read_bytes())
    need(manifest.get("name") == "pyright" and manifest.get("version") == PIN["pyright"],
         "PYRIGHT_NPM_PACKAGE_VERSION_DRIFT")
    reported["pyright-npm-package-json"] = digest(package.read_bytes())
    return reported


def pyright_scan(binary: Path, project: Path, source: Path, *,
                 expect_errors: bool, required_rules: tuple[str, ...],
                 extra_source: Path | None = None) -> tuple[dict, bytes, int, str, str]:
    config = {"typeCheckingMode": "strict",
              "reportIncompatibleMethodOverride": "error",
              "reportMissingTypeStubs": "none",
              "include": ["contract.py"] + (["public_sdk.py"] if extra_source else [])}
    project.mkdir(parents=True, exist_ok=False)
    (project / "pyrightconfig.json").write_bytes(canonical(config))
    script = project / "contract.py"
    shutil.copyfile(source, script)
    if extra_source is not None:
        need(extra_source.name == "public_sdk.py" and extra_source.parent == FIXTURE,
             "UNTRUSTED_EXTRA_SDK_SOURCE")
        shutil.copyfile(extra_source, project / "public_sdk.py")
    def assert_copied_sources_unchanged() -> None:
        need(script.read_bytes() == source.read_bytes(),
             "PYRIGHT_SCANNED_SOURCE_BYTES_DRIFT")
        if extra_source is not None:
            need((project / "public_sdk.py").read_bytes() == extra_source.read_bytes(),
                 "PYRIGHT_SCANNED_SDK_BYTES_DRIFT")

    assert_copied_sources_unchanged()
    args = [str(binary.resolve()), "--project", str(project), "--pythonpath",
            sys.executable, "--outputjson"]
    started = datetime.now(timezone.utc).isoformat()
    run = subprocess.run(args, cwd=ROOT, capture_output=True, text=True,
                         timeout=120, check=False)
    finished = datetime.now(timezone.utc).isoformat()
    assert_copied_sources_unchanged()
    raw = run.stdout.encode()
    try:
        parsed = json.loads(raw)
    except (ValueError, UnicodeDecodeError) as exc:
        raise RuntimeError("PYRIGHT_INVALID_JSON " + run.stderr[:1000]) from exc
    need(isinstance(parsed, dict) and isinstance(parsed.get("generalDiagnostics"), list)
         and isinstance(parsed.get("summary"), dict), "PYRIGHT_MALFORMED_JSON")
    need(parsed.get("version") == PIN["pyright"], "PYRIGHT_REPORT_VERSION_DRIFT")
    summary = parsed["summary"]
    errors = _validate_pyright_diagnostics(
        parsed, project, extra_source=extra_source)
    rules = {x.get("rule") for x in errors}
    if expect_errors:
        need(run.returncode == 1 and int(summary.get("errorCount", 0)) >= 1,
             "NEGATIVE_SDK_SIGNATURE_NOT_REJECTED")
        need(set(required_rules).issubset(rules),
             "NEGATIVE_REQUIRED_TYPE_DIAGNOSTICS_MISSING "
             + repr(sorted(set(required_rules) - rules)))
    else:
        need(run.returncode == 0 and not errors and int(summary.get("errorCount", -1)) == 0,
             "VALID_SDK_TYPES_REJECTED")
    need(not parsed.get("fatalErrorOccurred") and not parsed.get("configParseErrorOccurred"),
         "PYRIGHT_INCOMPLETE_OR_CONFIG_ERROR")
    # Detailed diagnostics and source identity are retained in the raw JSON.
    print(f"PYRIGHT_{'NEGATIVE' if expect_errors else 'POSITIVE'}=PASS "
          f"diagnostics={len(errors)} rules={sorted(str(x) for x in rules)}")
    return parsed, raw, run.returncode, started, finished


def run_gate(binary: Path, project: Path, selected_source: Path,
             *, negative: bool, snapshot_id: str, output: Path,
             required_rules: tuple[str, ...] = (CHECKED_RULE,),
             extra_source: Path | None = None) -> dict:
    parsed, raw, exit_code, started, finished = pyright_scan(
        binary, project, selected_source, expect_errors=negative,
        required_rules=required_rules, extra_source=extra_source)
    source_bytes = selected_source.read_bytes()
    selected = "fixtures/python-sdk/" + selected_source.name
    source_digests = {selected: digest(source_bytes)}
    if extra_source is not None:
        source_digests["fixtures/python-sdk/" + extra_source.name] = digest(
            extra_source.read_bytes())
    selected_files = [{"path": p, "sha256": d}
                      for p, d in sorted(source_digests.items())]
    tool_path = ROOT / "node_modules/pyright/dist/pyright.js"
    need(tool_path.is_file(), "PINNED_PYRIGHT_DIST_MISSING")
    config_bytes = (project / "pyrightconfig.json").read_bytes()
    tool_doc = {
        "name": "Pyright", "version": PIN["pyright"],
        "binary_sha256": digest(tool_path.read_bytes()), "adapter_version": "0.1",
        "invocation_sha256": digest(canonical(["pyright", "project", "pythonpath", "outputjson", "strict"])),
        "ruleset_sha256": digest(config_bytes),
        "exit_classifier": "pyright-1.1.414-outputjson-exit-v1",
    }
    findings = []
    for issue in parsed["generalDiagnostics"]:
        if issue.get("rule") not in required_rules:
            continue
        span = issue.get("range") or {}
        start = span.get("start") or {}
        file_name = _attested_diagnostic_file(
            issue, project, extra_source=extra_source)
        source_path = ("fixtures/python-sdk/" + extra_source.name
                       if file_name == "public_sdk.py" and extra_source is not None
                       else selected)
        need(source_path in source_digests, "PYRIGHT_DIAGNOSTIC_OUTSIDE_ATTESTED_SOURCE")
        findings.append({
            "kind": "TYPECHECK_DIAGNOSTIC", "rule_id": str(issue["rule"]),
            "severity": "ERROR" if issue.get("severity") == "error" else "WARNING",
            "path": source_path, "line": int(start.get("line", 0)) + 1,
            "message": str(issue.get("message") or "Pyright diagnostic"),
            "native_status": str(issue.get("rule")),
        })
    if negative:
        need(bool(findings), "NEGATIVE_OVERRIDE_EVIDENCE_MISSING")
    record = {
        "schema_version": "0.1", "snapshot_id": snapshot_id, "tool": tool_doc,
        "execution": {
            "state": "COMPLETED", "exit_code": exit_code,
            "exit_classification": "VALID_RESULT",
            "started_at": started, "finished_at": finished,
        },
        "scope": {
            "expected_files": selected_files,
            "scanned_files": selected_files,
            "skipped_files": [], "parser_errors": [],
            "required_rules": list(required_rules),
            "evaluated_rules": list(required_rules),
        },
        "raw_artifact": {
            "uri": "artifact://ci/" + selected_source.stem + ".json",
            "sha256": digest(raw), "media_type": "application/json",
        },
        "observations": findings,
    }
    registry = ResourceRegistry(ROOT)
    evidence = parse_external_evidence(
        record, registry.load_json("external_evidence_envelope_schema"))
    trust = ToolIdentity(**tool_doc)
    admission = assess_external_evidence(
        evidence, expected_snapshot_id=snapshot_id,
        expected_files=source_digests,
        expected_tool=trust, expected_rules=list(required_rules), raw_artifact=raw,
    )
    need(admission.status == "ADMISSIBLE", "PYRIGHT_ADMISSION_FAILED " + str(admission))
    policy_raw = {
        "schema_version": "0.1",
        "policy_id": "controlled-sdk-typecheck-" + selected_source.stem,
        "snapshot_id": snapshot_id,
        "source_files": selected_files,
        "requirements": [{
            "id": "sdk.override", "scope": "fixtures/python-sdk/**",
            "tool": tool_doc, "rule_ids": list(required_rules),
            "predicate": "TYPE_NO_ERRORS", "exceptions": [],
        }],
    }
    policy = parse_gate_policy(policy_raw, registry.load_json("evidence_gate_schema"))
    verdict = evaluate_gate(
        policy, runs={"sdk.override": EvidenceRun(evidence, raw)},
        expected_policy_sha256=policy.fingerprint(), expected_snapshot_id=snapshot_id,
        expected_sources=source_digests,
        evaluated_at=datetime.now(timezone.utc).isoformat(),
    )
    wanted = ("FAIL", "BLOCK") if negative else ("PASS", "ALLOW")
    need((verdict.status, verdict.authorization) == wanted,
         "TYPE_GATE_WRONG_VERDICT " + verdict.canonical_json())
    print("SDK_TYPE_GATE=PASS testcase=" + selected_source.stem
          + " decision=" + verdict.status + "/" + verdict.authorization)
    (output / (selected_source.stem + "-pyright.json")).write_bytes(raw)
    return {
        "test": selected_source.name, "source_sha256": digest(source_bytes),
        "selected_sources": selected_files, "required_rules": list(required_rules),
        "tool": tool_doc, "admission": admission.to_document(),
        "gate": verdict.to_document(), "native_diagnostic_count": len(parsed["generalDiagnostics"]),
        "actual_report_sha256": digest(raw),
    }


def test_runtime(contract: dict) -> dict:
    # This execution is explicitly controlled and is never used on untrusted code.
    from pydantic import AliasChoices, AliasPath, BaseModel, ConfigDict, Field, ValidationError, computed_field
    from pydantic.alias_generators import to_camel
    from sqlalchemy import Integer, String, create_engine, event, inspect
    from sqlalchemy.orm import DeclarativeBase, Session, mapped_column
    from sqlalchemy.schema import CreateTable

    class Payload(BaseModel):
        model_config = ConfigDict(populate_by_name=True)
        item_id: int = Field(
            validation_alias=AliasChoices("legacyId", "newId"),
            serialization_alias="itemId",
        )
        quantity: int

        @computed_field
        @property
        def total(self) -> int:
            return self.item_id * self.quantity

    dto = contract["expected_pydantic"]
    payload = Payload.model_validate(dto["input"])
    need(payload.model_dump(by_alias=True) == dto["serialization_by_alias"],
         "PYDANTIC_OUTPUT_ALIAS_DRIFT")
    need(payload.model_dump(by_alias=False) == dto["serialization_by_name"],
         "PYDANTIC_OUTPUT_NAME_DRIFT")
    need(Payload.model_validate(dto["alternate_input"]).model_dump(by_alias=True)
         == dto["serialization_by_alias"], "PYDANTIC_ALIAS_CHOICES_DRIFT")

    class Collision(BaseModel):
        first: int = Field(serialization_alias="sameKey")
        second: int = Field(serialization_alias="sameKey")

    colliding = Collision(first=1, second=2).model_dump(by_alias=True)
    need(len(colliding) != 2, "COLLISION_NEGATIVE_CONTROL_FAILED")

    # Controlled, direction-specific AliasPath and alias_generator witnesses.
    # A serializer's output aliases are not automatically accepted as input.
    class NestedPayload(BaseModel):
        item_code: str = Field(serialization_alias="itemCode")

    class EnvelopePayload(BaseModel):
        model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)
        order_id: int = Field(
            validation_alias=AliasPath("envelope", "orderId"),
            serialization_alias="orderId",
        )
        nested: NestedPayload
        private_note: str = Field(exclude=True)

    nested_contract = contract["expected_pydantic_nested"]
    need(nested_contract["mapping_scope"] == "CONTROLLED_DIRECTIONAL_MAPPING_ONLY",
         "UNREVIEWED_NESTED_MAPPING_SCOPE")
    nested = EnvelopePayload.model_validate(nested_contract["input"])
    nested_by_alias = nested.model_dump(by_alias=True)
    nested_by_name = nested.model_dump(by_alias=False)
    need(nested_by_alias == nested_contract["serialization_by_alias"],
         "PYDANTIC_NESTED_ALIAS_OR_EXCLUSION_DRIFT")
    need(nested_by_name == nested_contract["serialization_by_name"],
         "PYDANTIC_NESTED_FIELD_NAME_DRIFT")
    need("privateNote" not in nested_by_alias and "private_note" not in nested_by_name,
         "EXCLUDED_FIELD_LEAKED_IN_DTO")
    alias_path = EnvelopePayload.model_fields["order_id"].validation_alias
    need(isinstance(alias_path, AliasPath) and alias_path.path == ["envelope", "orderId"],
         "ALIAS_PATH_EFFECTIVE_MAPPING_DRIFT")
    need(EnvelopePayload.model_fields["private_note"].alias == "privateNote",
         "ALIAS_GENERATOR_EFFECTIVE_MAPPING_DRIFT")
    try:
        EnvelopePayload.model_validate(nested_contract["invalid_missing_alias_path"])
    except ValidationError:
        pass
    else:
        raise RuntimeError("MISSING_ALIAS_PATH_NEGATIVE_CONTROL_FAILED")

    class Base(DeclarativeBase):
        pass

    class Record(Base):
        __tablename__ = "sdk_records"
        id = mapped_column(Integer, primary_key=True)
        python_label = mapped_column("DB_LABEL", String(30), key="db_key")
        quantity = mapped_column(Integer)

    observed = []
    @event.listens_for(Record, "before_insert")
    def before_insert(_mapper, _connection, target):
        observed.append(target.python_label)

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(Record(id=1, python_label="sample", quantity=2))
        session.commit()
        value = session.get(Record, 1)
        need(value is not None and value.python_label == "sample",
             "SQLALCHEMY_RUNTIME_MAPPING_FAILED")
    need(len(observed) == contract["expected_sqlalchemy"]["expected_event_count"],
         "SQLALCHEMY_CALLBACK_NOT_DISPATCHED")

    fields = []
    for prop in inspect(Record).attrs:
        if hasattr(prop, "columns"):
            column = prop.columns[0]
            fields.append({"attribute": prop.key, "column_key": column.key,
                           "physical_name": column.name})
    fields.sort(key=lambda x: x["attribute"])
    expected = sorted(contract["expected_sqlalchemy"]["columns"],
                      key=lambda x: x["attribute"])
    need(fields == expected, "ORM_ATTRIBUTE_COLUMN_MAPPING_DRIFT")
    reflected = sorted(x["name"] for x in inspect(engine).get_columns("sdk_records"))
    need(reflected == sorted(contract["expected_sqlalchemy"]["required_sqlite_reflection_columns"]),
         "SQLITE_REFLECTION_DRIFT")
    ddl = str(CreateTable(Record.__table__).compile(engine))
    need(all(fragment in ddl for fragment in contract["expected_sqlalchemy"]["baseline_ddl"]),
         "PINNED_BASELINE_DDL_DRIFT")
    # A negative DDL baseline proves our comparator is not just checking metadata presence.
    need(ddl != ddl.replace("DB_LABEL", "ALTERED_LABEL"), "DDL_NEGATIVE_CONTROL_FAILED")
    return {
        "scope": "CONTROLLED_FIXTURE_ONLY",
        "pydantic_alias_mapping": dto,
        "pydantic_nested_directional_mapping": nested_contract,
        "sqlalchemy_fields": fields,
        "sqlite_reflected_columns": reflected,
        "sqlite_ddl_sha256": digest(ddl.encode()),
        "callback_dispatch_count": len(observed),
        "external_api_consumer_compatibility": "NOT_EVALUATED",
        "production_db_migration_compatibility": "NOT_EVALUATED",
    }



def test_extended_orm(contract: dict) -> dict:
    """Real pinned SQLAlchemy 2.0.50 + SQLite controlled inheritance/migration.

    No production DB history, external ORM consumer or deployed schema is used.
    """
    from sqlalchemy import Computed, ForeignKey, Integer, String, create_engine, inspect
    from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

    expected = contract["expected_sqlalchemy_extended"]
    need(expected["scope"] == "CONTROLLED_IN_MEMORY_SQLITE_ONLY",
         "UNREVIEWED_ORM_MIGRATION_SCOPE")

    class Base(DeclarativeBase):
        pass

    class Parent(Base):
        __tablename__ = "sdk_parent"
        id = mapped_column(Integer, primary_key=True)
        kind = mapped_column(String(16))
        label = mapped_column(String(30))
        __mapper_args__ = {"polymorphic_on": kind, "polymorphic_identity": "parent"}

    class Child(Parent):
        __tablename__ = "sdk_child"
        id = mapped_column(ForeignKey("sdk_parent.id"), primary_key=True)
        child_label = mapped_column(String(30))
        __mapper_args__ = {"polymorphic_identity": "child"}

    class ComputedRow(Base):
        __tablename__ = "sdk_computed"
        id = mapped_column(Integer, primary_key=True)
        quantity = mapped_column(Integer)
        doubled = mapped_column(Integer, Computed("quantity * 2"))

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add_all([
            Child(id=7, label="base", child_label="derived"),
            ComputedRow(id=8, quantity=3),
        ])
        session.commit()
        parent = session.get(Parent, 7)
        computed = session.get(ComputedRow, 8)
        need(type(parent).__name__ == "Child" and parent.child_label == "derived",
             "JOINED_INHERITANCE_RUNTIME_MAPPING_DRIFT")
        need(computed is not None and computed.doubled == expected["computed_value"],
             "COMPUTED_COLUMN_RUNTIME_DRIFT")

    before = sorted(c["name"] for c in inspect(engine).get_columns("sdk_parent"))
    need(before == sorted(expected["before_columns"]),
         "VERSIONED_SQLITE_BASELINE_DRIFT")
    foreign_keys = inspect(engine).get_foreign_keys("sdk_child")
    need(any(fk["referred_table"] == "sdk_parent"
             and fk["constrained_columns"] == ["id"] for fk in foreign_keys),
         "JOINED_INHERITANCE_FOREIGN_KEY_DRIFT")
    computed_columns = inspect(engine).get_columns("sdk_computed")
    need(any(c["name"] == "doubled" and c.get("computed") for c in computed_columns),
         "SQLITE_COMPUTED_COLUMN_REFLECTION_DRIFT")

    with engine.begin() as connection:
        connection.exec_driver_sql("ALTER TABLE sdk_parent ADD COLUMN optional_note TEXT")
    after = sorted(c["name"] for c in inspect(engine).get_columns("sdk_parent"))
    added, removed = sorted(set(after) - set(before)), sorted(set(before) - set(after))
    migration = expected["migration"]
    need(migration["from"] == "fixture_v0" and migration["to"] == "fixture_v1",
         "UNVERSIONED_CONTROLLED_MIGRATION")
    def verify_migration(columns: list[str], added_expected: list[str],
                         removed_expected: list[str]) -> None:
        need(after == sorted(columns)
             and added == added_expected and removed == removed_expected,
             "VERSIONED_SQLITE_MIGRATION_DRIFT")
    verify_migration(expected["after_columns"],
                     migration["added_columns"], migration["removed_columns"])
    # Negative: the exact same reflected DB cannot satisfy a forged migration.
    try:
        verify_migration(expected["after_columns"],
                         ["renamed_or_missing_column"], migration["removed_columns"])
    except RuntimeError as exc:
        need(str(exc) == "VERSIONED_SQLITE_MIGRATION_DRIFT",
             "MIGRATION_NEGATIVE_WRONG_FAILURE")
    else:
        raise RuntimeError("MIGRATION_NEGATIVE_CONTROL_FAILED")
    print("SQLALCHEMY_EXTENDED=PASS inheritance=JOINED computed=REFLECTED "
          "migration=fixture_v0_to_v1 compatibility=CONTROLLED_ONLY")
    engine.dispose()
    return {
        "scope": "CONTROLLED_IN_MEMORY_SQLITE_ONLY",
        "inheritance": "JOINED_RUNTIME_AND_FOREIGN_KEY_OBSERVED",
        "computed_value": expected["computed_value"],
        "before_columns": before,
        "after_columns": after,
        "migration": {"from": migration["from"], "to": migration["to"],
                      "added_columns": added, "removed_columns": removed},
        "external_schema_history": "NOT_EVALUATED",
        "production_migration_compatibility": "NOT_EVALUATED",
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--pyright", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    need(args.pyright.is_file(), "PYRIGHT_CLI_NOT_FOUND")
    versions = check_versions()
    contract_bytes = (FIXTURE / "external-contract-v0.1.json").read_bytes()
    contract = json.loads(contract_bytes)
    need(contract["scope"] == "CONTROLLED_PYTHON_SDK_FIXTURE_ONLY"
         and contract["packages"] == PIN, "EXTERNAL_CONTRACT_PIN_DRIFT")
    args.output.mkdir(parents=True, exist_ok=True)
    run = subprocess.run([str(args.pyright.resolve()), "--version"],
                         cwd=ROOT, capture_output=True, text=True, check=False, timeout=60)
    need(run.returncode == 0 and PIN["pyright"] in run.stdout + run.stderr,
         "PYRIGHT_CLI_VERSION_DRIFT")
    snapshot = "git:HyungseonSong-plasma/codeQA@"
    import os
    snapshot += os.getenv("GITHUB_SHA", "trusted-local-fixture")
    with tempfile.TemporaryDirectory(prefix="codeqa-pyright-sdk-") as tmp:
        tmpdir = Path(tmp)
        positive = run_gate(
            args.pyright, tmpdir / "positive",
            FIXTURE / "valid_contract.py", negative=False,
            snapshot_id=snapshot, output=args.output)
        negative = run_gate(
            args.pyright, tmpdir / "negative",
            FIXTURE / "invalid_override.py", negative=True,
            snapshot_id=snapshot, output=args.output)
        advanced_rules = (CHECKED_RULE, "reportAssignmentType", "reportCallIssue")
        advanced_positive = run_gate(
            args.pyright, tmpdir / "advanced-positive",
            FIXTURE / "valid_advanced_contract.py", negative=False,
            required_rules=advanced_rules, extra_source=FIXTURE / "public_sdk.py",
            snapshot_id=snapshot, output=args.output)
        advanced_negative = run_gate(
            args.pyright, tmpdir / "advanced-negative",
            FIXTURE / "invalid_advanced_contract.py", negative=True,
            required_rules=advanced_rules, extra_source=FIXTURE / "public_sdk.py",
            snapshot_id=snapshot, output=args.output)
    runtime = test_runtime(contract)
    runtime["sqlalchemy_extended"] = test_extended_orm(contract)
    result = {
        "version": "0.1", "source_snapshot": snapshot,
        "contract_sha256": digest(contract_bytes),
        "installed_distribution_metadata_sha256": versions,
        "typechecker": {"version": PIN["pyright"], "positive": positive,
                        "negative": negative,
                        "advanced_positive": advanced_positive,
                        "advanced_negative": advanced_negative,
                        "advanced_scope": "CONTROLLED_PINNED_PYDANTIC_TYPES_ONLY"},
        "runtime": runtime,
        "limitations": ["No actual consumer SDK public API baseline",
                        "No production DB migration verification",
                        "No automatic import or execution of untrusted third-party code",
                        "Only fixed synthetic SDK/ORM models were runtime executed"],
    }
    # Public benchmark reads only independently pinned source bytes. It NEVER
    # imports the upstream app or executes its migrations/install scripts.
    public_run = subprocess.run(
        [sys.executable, str(ROOT / ".github/scripts/public_api_benchmark.py"),
         "--output", str(args.output)],
        cwd=ROOT, capture_output=True, text=True, check=False, timeout=240)
    print(public_run.stdout, end="")
    need(public_run.returncode == 0, "PUBLIC_BENCHMARK_FAILED "
         + (public_run.stderr + public_run.stdout)[-3000:])
    result["public_benchmark"] = json.loads(
        (args.output / "public-api-benchmark.json").read_text(encoding="utf-8"))
    result["limitations"].append(
        "Pinned FastAPI TypeScript consumer source is not a Python SDK or a deployed API/DB")
    sdk_run = subprocess.run(
        [sys.executable, str(ROOT / ".github/scripts/public_python_sdk_benchmark.py"),
         "--output", str(args.output), "--pyright", str(args.pyright)],
        cwd=ROOT, capture_output=True, text=True, check=False, timeout=240)
    print(sdk_run.stdout, end="")
    need(sdk_run.returncode == 0, "PUBLIC_PYTHON_SDK_SOURCE_FAILED "
         + (sdk_run.stderr + sdk_run.stdout)[-3000:])
    result["public_python_sdk"] = json.loads(
        (args.output / "public-python-sdk-benchmark.json").read_text(encoding="utf-8"))
    result["limitations"].append(
        "Stripe 16.0.0 exact public SDK/consumer source attested; real external "
        "Pyright typechecking, callback dispatch and metaclass remain NOT_EVALUATED")
    (args.output / "sdk-conformance.json").write_bytes(
        json.dumps(result, indent=2, sort_keys=True).encode() + b"\n")
    print("PINNED_PYTHON_SDK=PASS pyright=" + PIN["pyright"]
          + " pydantic=" + PIN["Pydantic"] + " sqlalchemy=" + PIN["SQLAlchemy"]
          + " compatibility=CONTROLLED_ONLY")


if __name__ == "__main__":
    main()
