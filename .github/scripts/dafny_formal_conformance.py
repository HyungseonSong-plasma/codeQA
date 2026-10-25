#!/usr/bin/env python3
"""Pinned real Dafny verifier + Python codegen conformance for issue #102.

This exercises #98 Evidence and #99 Gate against a trusted synthetic fixture.
It does NOT make a hand-translated C++/Python implementation formally verified.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from dataclasses import asdict
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

from codeqa.core.external_evidence import (
    ToolIdentity, assess_external_evidence, parse_external_evidence,
)
from codeqa.evaluation.evidence_gate import (
    EvidenceRun, evaluate_gate, parse_gate_policy,
)
from codeqa.evaluation.formal_binding import parse_binding, verify_binding
from codeqa.evaluation.formal_proof_receipt import assess_formal_proof_evidence
from codeqa.evaluation.formal_generated_gate import (
    evaluate_generated_fixture_gate, parse_generated_fixture_policy,
    python_tree_manifest,
)
from codeqa.infrastructure.resources import ResourceRegistry


ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = ROOT / "fixtures/formal/pinned-dafny-v0.1.json"


def digest(data: bytes) -> str:
    return sha256(data).hexdigest()


def canonical(obj: object) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def python_bundle_manifest(root: Path) -> bytes:
    """Byte-bound, path-bound complete generated Python source tree."""
    files = sorted(p for p in root.rglob("*.py") if p.is_file())
    if not files:
        raise RuntimeError("missing generated Python sources")
    return canonical([
        {"path": p.relative_to(root).as_posix(), "sha256": digest(p.read_bytes())}
        for p in files
    ])


def run(args: list[str], cwd: Path, *, expected_ok: bool) -> subprocess.CompletedProcess[str]:
    # Never shell out through a shell: only the caller-pinned local Dafny binary.
    p = subprocess.run(args, cwd=cwd, capture_output=True, text=True,
                       timeout=120, check=False)
    if expected_ok and p.returncode != 0:
        raise RuntimeError(f"command failed {args!r} exit={p.returncode}:\n{p.stdout}\n{p.stderr}")
    if not expected_ok and p.returncode == 0:
        raise RuntimeError(f"negative Dafny fixture unexpectedly verified: {args!r}")
    return p


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dafny", type=Path, required=True)
    ap.add_argument("--release-archive", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()

    manifest_bytes = MANIFEST_PATH.read_bytes()
    manifest = json.loads(manifest_bytes)
    spec_path = ROOT / manifest["source_path"]
    spec_bytes = spec_path.read_bytes()
    if digest(spec_bytes) != manifest["source_sha256"]:
        raise RuntimeError("pinned source SHA mismatch; reviewed fixture source changed")
    if digest(args.release_archive.read_bytes()) != manifest["release_archive_sha256"]:
        raise RuntimeError("Dafny upstream release archive digest mismatch")
    if not args.dafny.is_file():
        raise RuntimeError("missing pinned Dafny CLI binary")
    cli = str(args.dafny.resolve())
    version = run([cli, "--version"], ROOT, expected_ok=True)
    if manifest["dafny_version"] not in version.stdout + version.stderr:
        raise RuntimeError("Dafny executable version does not match pin")
    tool_digest = digest(args.dafny.read_bytes())
    args.output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="codeqa-real-dafny-") as temp:
        build_root = Path(temp)
        proof_spec = build_root / "payment_add_one.dfy"
        proof_spec.write_bytes(spec_bytes)
        verify_args = [cli, "verify", proof_spec.name]
        verified_started = datetime.now(timezone.utc).isoformat()
        verified = run(verify_args, build_root, expected_ok=True)
        verified_finished = datetime.now(timezone.utc).isoformat()
        full_log = verified.stdout + verified.stderr
        success = re.search(r"(\d+) verified,\s*0 errors?", full_log, re.IGNORECASE)
        if not success or int(success.group(1)) < 1:
            raise RuntimeError("Dafny did not report a positive number of verified obligations and zero errors:\n" + full_log)

        # A nontrivial negative control demonstrates that the actual solver
        # rejects a changed body violating the *unchanged* postcondition.
        adversarial = spec_bytes.decode("utf-8").replace(
            "y := x + 1;", "y := x + 2;",
        )
        if adversarial == spec_bytes.decode("utf-8"):
            raise RuntimeError("negative mutation site absent")
        bad = build_root / "payment_mutated.dfy"
        bad.write_text(adversarial, encoding="utf-8")
        rejected = run([cli, "verify", bad.name], build_root, expected_ok=False)
        fail_log = rejected.stdout + rejected.stderr
        if not re.search(r"\b[1-9]\d* errors?\b|postcondition might not hold|assertion might not hold", fail_log, re.IGNORECASE):
            raise RuntimeError("negative case exited nonzero for an unrecognized reason: " + fail_log)

        built = run([cli, "build", "--target:py", proof_spec.name], build_root, expected_ok=True)
        # Dafny 4.11.0 generates a Python package: module_.py, __main__.py
        # and the _dafny runtime; it does NOT create payment_add_one.py.
        generated_dir = build_root / "payment_add_one-py"
        if not (generated_dir / "__main__.py").is_file():
            raise RuntimeError("missing Dafny-generated __main__.py; build stdout="
                               + repr(built.stdout) + " files="
                               + repr([str(p.relative_to(build_root))
                                       for p in build_root.rglob("*.py")]))
        generated = python_bundle_manifest(generated_dir)
        runtime = run([sys.executable, str(generated_dir / "__main__.py")],
                      generated_dir, expected_ok=True)
        if runtime.stdout.strip() != manifest["required_runtime_output"]:
            raise RuntimeError(f"wrong generated Python behavior: {runtime.stdout!r}")
        deployed = args.output / "deployed_payment_add_one-py"
        shutil.copytree(generated_dir, deployed, ignore=shutil.ignore_patterns(
            "__pycache__", "*.pyc",
        ))
        deployed_bytes = python_bundle_manifest(deployed)
        if generated != deployed_bytes:
            raise RuntimeError("copy to fixture deployment changed generated Python source tree")

        build_config = {
            "verify_command": ["dafny", "verify", "payment_add_one.dfy"],
            "build_command": ["dafny", "build", "--target:py", "payment_add_one.dfy"],
            "source_sha256": digest(spec_bytes),
            "expected_output": manifest["required_runtime_output"],
        }
        build_config_sha = digest(canonical(build_config))
        attestation_id = "local-pinned-cli-workflow:" + os.environ.get("GITHUB_SHA", "local")
        record = {
            "schema_version": "0.1",
            "mode": "GENERATED_CODE_MATCH",
            "specification": {"role": "specification", "path": manifest["source_path"], "sha256": digest(spec_bytes)},
            "generated": {"role": "generated", "path": "build/payment_add_one-py", "sha256": digest(generated)},
            "deployed": {"role": "deployed", "path": "dist/payment_add_one-py", "sha256": digest(deployed_bytes)},
            "toolchain_id": "dafny@" + manifest["dafny_version"] + ":target=py",
            "toolchain_sha256": tool_digest,
            "build_configuration_sha256": build_config_sha,
            "attestation_id": attestation_id,
            "attested_properties": [manifest["required_property"]],
        }
        typed = parse_binding(record)
        common = dict(
            specification_bytes=spec_bytes,
            generated_bytes=generated,
            deployed_bytes=deployed_bytes,
            expected_toolchain_sha256=tool_digest,
            expected_build_configuration_sha256=build_config_sha,
            expected_attestation_id=attestation_id,
            required_properties=(manifest["required_property"],),
        )
        identity = verify_binding(typed, **common)
        if identity.status != "IDENTITY_MATCH":
            raise RuntimeError("actual verified/generated/deployed chain did not match: " + str(identity))
        # This MUST be blocked: unchanged Dafny proof cannot verify tampered
        # deployment even though the standalone verification succeeded.
        corrupted = verify_binding(typed, **{**common, "deployed_bytes": deployed_bytes + b"\n# defect\n"})
        if corrupted.status != "BINDING_BROKEN":
            raise RuntimeError("mutated deployed file was falsely admitted")
        stale = verify_binding(typed, **{**common, "specification_bytes": spec_bytes + b"\n// drift\n"})
        if stale.status != "BINDING_BROKEN":
            raise RuntimeError("stale verified specification was falsely admitted")

        # Evidence v0.1 is admissible for its actually scanned .dfy source,
        # NOT for production implementation correctness.
        source_hash = digest(spec_bytes)
        raw = full_log.encode("utf-8")
        rule = "dafny:verified-selected-program"
        tool = {
            "name": "Dafny", "version": manifest["dafny_version"],
            "binary_sha256": tool_digest,
            "adapter_version": "0.1",
            "invocation_sha256": digest(canonical(verify_args[1:])),
            "ruleset_sha256": digest(manifest_bytes),
            "exit_classifier": "dafny-4.11.0-verify-summary-v1",
        }
        snapshot_id = "git:HyungseonSong-plasma/codeQA@" + os.environ.get("GITHUB_SHA", "local-fixture")
        evidence = {
            "schema_version": "0.1", "snapshot_id": snapshot_id,
            "tool": tool,
            "execution": {
                "state": "COMPLETED", "exit_code": verified.returncode,
                "exit_classification": "VALID_RESULT",
                "started_at": verified_started,
                "finished_at": verified_finished,
            },
            "scope": {
                "expected_files": [{"path": manifest["source_path"], "sha256": source_hash}],
                "scanned_files": [{"path": manifest["source_path"], "sha256": source_hash}],
                "skipped_files": [], "parser_errors": [],
                "required_rules": [rule], "evaluated_rules": [rule],
            },
            "raw_artifact": {
                "uri": "artifact://ci/dafny-verify.log",
                "sha256": digest(raw), "media_type": "text/plain",
            },
            "observations": [{
                "kind": "FORMAL_PROOF_RESULT",
                "obligation_id": manifest["required_property"],
                "path": manifest["source_path"], "source_sha256": source_hash,
                "native_status": "VERIFIED",
                "assumptions": ["Dafny 4.11.0 trusted verifier/compiler/solver and Python runtime"],
                "counterexample_sha256": None,
            }],
        }
        registry = ResourceRegistry(ROOT)
        env = parse_external_evidence(evidence, registry.load_json("external_evidence_envelope_schema"))
        admitted = assess_external_evidence(
            env, expected_snapshot_id=snapshot_id,
            expected_files={manifest["source_path"]: source_hash},
            expected_tool=ToolIdentity(**tool), expected_rules=[rule],
            raw_artifact=raw, purpose="SOURCE_ANALYSIS",
        )
        if admitted.status != "ADMISSIBLE":
            raise RuntimeError("source proof receipt rejected: " + str(admitted))
        # The actual Dafny verifier receipt is source-scoped. The bundled
        # solver executable/version is not independently attested here, so
        # do not silently fill in a fictitious solver identity.
        proof_receipt = assess_formal_proof_evidence(
            env, expected_snapshot_id=snapshot_id,
            expected_specification_path=manifest["source_path"],
            expected_specification_sha256=source_hash,
            expected_tool=ToolIdentity(**tool), expected_rules=(rule,),
            required_obligations=(manifest["required_property"],),
            accepted_assumptions=tuple(manifest["accepted_assumptions"]),
            raw_verifier_log=raw, observed_solver=None, expected_solver=None,
        )
        if (proof_receipt.status != "NOT_EVALUATED"
                or proof_receipt.implementation_authorization != "BLOCK"
                or "SOLVER_PROVENANCE_NOT_EVALUATED" not in proof_receipt.reasons):
            raise RuntimeError("solver/deployment uncertainty was incorrectly promoted")
        policy_raw = {
            "schema_version": "0.1",
            "policy_id": "pinned-dafny-formal-v0.1",
            "snapshot_id": snapshot_id,
            "source_files": [{"path": manifest["source_path"], "sha256": source_hash}],
            "requirements": [{
                "id": "payment.proof", "scope": manifest["source_path"],
                "tool": tool, "rule_ids": [rule],
                "predicate": "FORMAL_IMPLEMENTATION_VERIFIED",
                "exceptions": [],
            }],
        }
        policy = parse_gate_policy(policy_raw, registry.load_json("evidence_gate_schema"))
        gate = evaluate_gate(
            policy, runs={"payment.proof": EvidenceRun(env, raw)},
            expected_policy_sha256=policy.fingerprint(),
            expected_snapshot_id=snapshot_id,
            expected_sources={manifest["source_path"]: source_hash},
            evaluated_at=datetime.now(timezone.utc).isoformat(),
        )
        if gate.status != "UNKNOWN" or gate.authorization != "BLOCK":
            raise RuntimeError("formal implementation policy Gate was falsely allowed: " + gate.canonical_json())

        # Separate, opt-in policy can PASS only a pinned generated *fixture*,
        # never the production implementation verified predicate in #99.
        fixture_policy_doc = {
            "version": "0.1",
            "scope": "CONTROLLED_GENERATED_PYTHON_FIXTURE",
            "snapshot_id": snapshot_id,
            "specification_path": manifest["source_path"],
            "specification_sha256": manifest["source_sha256"],
            "required_properties": [manifest["required_property"]],
            "required_rule_ids": manifest["required_rule_ids"],
            "accepted_assumptions": manifest["accepted_assumptions"],
            "required_generated_paths": manifest["required_generated_paths"],
            "tool": tool,
            "expected_build_configuration_sha256": build_config_sha,
            "attestation_id": attestation_id,
        }
        fixture_policy = parse_generated_fixture_policy(fixture_policy_doc)
        def python_files(folder: Path) -> dict[str, bytes]:
            return {
                item.relative_to(folder).as_posix(): item.read_bytes()
                for item in sorted(folder.rglob("*.py")) if item.is_file()
            }

        gen_files = python_files(generated_dir)
        dep_files = python_files(deployed)
        if python_tree_manifest(gen_files) != generated:
            raise RuntimeError("generated source set does not match frozen manifest")
        frozen_args = {
            "policy": fixture_policy,
            "expected_policy_sha256": fixture_policy.fingerprint(),
            "expected_snapshot_id": snapshot_id,
            "expected_tool": ToolIdentity(**tool),
            "evidence": env, "raw_verifier_log": raw,
            "specification_bytes": spec_bytes,
            "generated_files": gen_files,
            "deployed_files": dep_files,
            "binding": typed,
        }
        fixture_gate = evaluate_generated_fixture_gate(**frozen_args)
        if (fixture_gate.status, fixture_gate.authorization) != (
            "PASS", "ALLOW_FIXTURE_ONLY",
        ):
            raise RuntimeError("controlled generated fixture incorrectly blocked: "
                               + fixture_gate.canonical_json())

        # Critical property: a still-green source proof does NOT authorize a
        # changed executable, extra generated module or stale source bytes.
        changed = dict(dep_files)
        changed["__main__.py"] = changed["__main__.py"] + b"\n# modified after proof\n"
        changed_gate = evaluate_generated_fixture_gate(
            **{**frozen_args, "deployed_files": changed},
        )
        if changed_gate.authorization != "BLOCK":
            raise RuntimeError("tampered deployed fixture incorrectly authorized")
        stale_gate = evaluate_generated_fixture_gate(
            **{**frozen_args, "specification_bytes": spec_bytes + b"\n// stale\n"},
        )
        if stale_gate.authorization != "BLOCK":
            raise RuntimeError("outdated Dafny specification incorrectly authorized")
        wrong_tool_gate = evaluate_generated_fixture_gate(
            **{**frozen_args, "expected_tool": None},
        )
        if wrong_tool_gate.authorization != "BLOCK":
            raise RuntimeError("untrusted verifier identity incorrectly authorized")

        (args.output / "verification.log").write_text(full_log, encoding="utf-8")
        (args.output / "negative-proof.log").write_text(fail_log, encoding="utf-8")
        (args.output / "codegen.log").write_text(built.stdout + built.stderr, encoding="utf-8")
        receipt = {
            "schema_version": "0.1",
            "assurance_scope": manifest["assurance_level"],
            "release_archive_sha256": digest(args.release_archive.read_bytes()),
            "dafny_cli_sha256": tool_digest,
            "dafny_cli_version_output": version.stdout.strip(),
            "specification_sha256": source_hash,
            "verifier_summary": success.group(0),
            "negative_verification_exit_code": rejected.returncode,
            "generated_python_sha256": digest(generated),
            "deployed_fixture_sha256": digest(deployed_bytes),
            "runtime_stdout": runtime.stdout.strip(),
            "binding": {**record, "result": asdict(identity)},
            "tampered_deployment_status": corrupted.status,
            "stale_spec_status": stale.status,
            "admission_source": asdict(admitted),
            "typed_formal_proof_receipt": proof_receipt.to_document(),
            "gate": gate.to_document(),
            "generated_fixture_gate": asdict(fixture_gate),
            "tampered_fixture_gate": asdict(changed_gate),
            "stale_fixture_gate": asdict(stale_gate),
            "limitations": [
                "No actual production deployment, signing or authenticated CI provenance",
                "Dafny's successful proof is relative to specification and trusted axioms",
                "Python runtime and compiler semantics are not formally validated",
                "External implementation verified policy intentionally remains UNKNOWN/BLOCK",
            ],
        }
        (args.output / "formal-evidence.json").write_bytes(
            json.dumps(receipt, indent=2, sort_keys=True).encode("utf-8") + b"\n"
        )
        print("PINNED_DAFNY=PASS verifier=" + manifest["dafny_version"]
              + " proof_verified=" + success.group(1)
              + " generated_python_sha256=" + digest(generated)
              + " runtime=" + runtime.stdout.strip()
              + " formal_gate=" + gate.status + "/" + gate.authorization
              + " fixture_gate=" + fixture_gate.status + "/" + fixture_gate.authorization)


if __name__ == "__main__":
    main()
