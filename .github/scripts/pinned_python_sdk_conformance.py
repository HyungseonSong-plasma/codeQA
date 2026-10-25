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


def pyright_scan(binary: Path, project: Path, *, expect_errors: bool) -> tuple[dict, bytes, int, str, str]:
    config = {"typeCheckingMode": "strict",
              "reportIncompatibleMethodOverride": "error",
              "reportMissingTypeStubs": "none",
              "include": ["contract.py"]}
    project.mkdir(parents=True, exist_ok=False)
    (project / "pyrightconfig.json").write_bytes(canonical(config))
    script = project / "contract.py"
    source = FIXTURE / ("invalid_override.py" if expect_errors else "valid_contract.py")
    shutil.copyfile(source, script)
    args = [str(binary.resolve()), "--project", str(project), "--pythonpath",
            sys.executable, "--outputjson"]
    started = datetime.now(timezone.utc).isoformat()
    run = subprocess.run(args, cwd=ROOT, capture_output=True, text=True,
                         timeout=120, check=False)
    finished = datetime.now(timezone.utc).isoformat()
    raw = run.stdout.encode()
    try:
        parsed = json.loads(raw)
    except (ValueError, UnicodeDecodeError) as exc:
        raise RuntimeError("PYRIGHT_INVALID_JSON " + run.stderr[:1000]) from exc
    need(isinstance(parsed, dict) and isinstance(parsed.get("generalDiagnostics"), list)
         and isinstance(parsed.get("summary"), dict), "PYRIGHT_MALFORMED_JSON")
    need(parsed.get("version") == PIN["pyright"], "PYRIGHT_REPORT_VERSION_DRIFT")
    summary = parsed["summary"]
    errors = [x for x in parsed["generalDiagnostics"] if x.get("severity") == "error"]
    rules = {x.get("rule") for x in errors}
    if expect_errors:
        need(run.returncode == 1 and int(summary.get("errorCount", 0)) >= 1,
             "NEGATIVE_SDK_SIGNATURE_NOT_REJECTED")
        need(CHECKED_RULE in rules, "NEGATIVE_OVERRIDE_NOT_DETECTED")
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
             *, negative: bool, snapshot_id: str, output: Path) -> dict:
    parsed, raw, exit_code, started, finished = pyright_scan(
        binary, project, expect_errors=negative)
    source_bytes = selected_source.read_bytes()
    selected = "fixtures/python-sdk/" + selected_source.name
    record_rule = CHECKED_RULE
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
        if issue.get("rule") != record_rule:
            continue
        span = issue.get("range") or {}
        start = span.get("start") or {}
        findings.append({
            "kind": "TYPECHECK_DIAGNOSTIC", "rule_id": record_rule,
            "severity": "ERROR" if issue.get("severity") == "error" else "WARNING",
            "path": selected, "line": int(start.get("line", 0)) + 1,
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
            "expected_files": [{"path": selected, "sha256": digest(source_bytes)}],
            "scanned_files": [{"path": selected, "sha256": digest(source_bytes)}],
            "skipped_files": [], "parser_errors": [],
            "required_rules": [record_rule], "evaluated_rules": [record_rule],
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
        expected_files={selected: digest(source_bytes)},
        expected_tool=trust, expected_rules=[record_rule], raw_artifact=raw,
    )
    need(admission.status == "ADMISSIBLE", "PYRIGHT_ADMISSION_FAILED " + str(admission))
    policy_raw = {
        "schema_version": "0.1",
        "policy_id": "controlled-sdk-typecheck-" + selected_source.stem,
        "snapshot_id": snapshot_id,
        "source_files": [{"path": selected, "sha256": digest(source_bytes)}],
        "requirements": [{
            "id": "sdk.override", "scope": selected,
            "tool": tool_doc, "rule_ids": [record_rule],
            "predicate": "TYPE_NO_ERRORS", "exceptions": [],
        }],
    }
    policy = parse_gate_policy(policy_raw, registry.load_json("evidence_gate_schema"))
    verdict = evaluate_gate(
        policy, runs={"sdk.override": EvidenceRun(evidence, raw)},
        expected_policy_sha256=policy.fingerprint(), expected_snapshot_id=snapshot_id,
        expected_sources={selected: digest(source_bytes)},
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
        "tool": tool_doc, "admission": admission.to_document(),
        "gate": verdict.to_document(), "native_diagnostic_count": len(parsed["generalDiagnostics"]),
        "actual_report_sha256": digest(raw),
    }


def test_runtime(contract: dict) -> dict:
    # This execution is explicitly controlled and is never used on untrusted code.
    from pydantic import AliasChoices, AliasPath, BaseModel, ConfigDict, Field, ValidationError, computed_field
    from pydantic.alias_generators import to_camel
    from sqlalchemy import Integer, String, create_engine, event, inspect
    from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column
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
    runtime = test_runtime(contract)
    result = {
        "version": "0.1", "source_snapshot": snapshot,
        "contract_sha256": digest(contract_bytes),
        "installed_distribution_metadata_sha256": versions,
        "typechecker": {"version": PIN["pyright"], "positive": positive,
                        "negative": negative},
        "runtime": runtime,
        "limitations": ["No actual consumer SDK public API baseline",
                        "No production DB migration verification",
                        "No automatic import or execution of untrusted third-party code",
                        "Only fixed synthetic SDK/ORM models were runtime executed"],
    }
    (args.output / "sdk-conformance.json").write_bytes(
        json.dumps(result, indent=2, sort_keys=True).encode() + b"\n")
    print("PINNED_PYTHON_SDK=PASS pyright=" + PIN["pyright"]
          + " pydantic=" + PIN["Pydantic"] + " sqlalchemy=" + PIN["SQLAlchemy"]
          + " compatibility=CONTROLLED_ONLY")


if __name__ == "__main__":
    main()
