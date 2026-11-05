#!/usr/bin/env python3
"""Real Pyright checks against an installed codeQA wheel outside its checkout.

Controlled codeQA consumer only. No third-party public SDK or production ABI
claim; negative native diagnostics must be witnessed, not synthesized.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory


PYRIGHT = "1.1.414"
RULES = ("reportArgumentType", "reportAssignmentType")


def require(ok: bool, reason: str) -> None:
    if not ok:
        raise RuntimeError(reason)


def run_typecheck(binary: Path, venv: Path, source: Path, project: Path,
                  *, negative: bool) -> dict[str, object]:
    project.mkdir(parents=True, exist_ok=False)
    config = {
        "typeCheckingMode": "strict",
        "pythonVersion": f"{sys.version_info.major}.{sys.version_info.minor}",
        "venvPath": str(venv.parent),
        "venv": venv.name,
        "reportMissingTypeStubs": "none",
        "include": ["consumer.py"],
    }
    (project / "pyrightconfig.json").write_text(
        json.dumps(config, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    shutil.copyfile(source, project / "consumer.py")
    completed = subprocess.run(
        [str(binary), "--project", str(project), "--outputjson"],
        capture_output=True, text=True, timeout=180, check=False,
    )
    try:
        parsed = json.loads(completed.stdout)
    except (ValueError, TypeError) as exc:
        raise RuntimeError("PYRIGHT_INSTALLED_CONSUMER_JSON_UNAVAILABLE") from exc
    require(isinstance(parsed, dict) and parsed.get("version") == PYRIGHT,
            "PYRIGHT_INSTALLED_CONSUMER_VERSION_DRIFT")
    require(not parsed.get("fatalErrorOccurred")
            and not parsed.get("configParseErrorOccurred"),
            "PYRIGHT_INSTALLED_CONSUMER_INCOMPLETE")
    summary = parsed.get("summary")
    issues = parsed.get("generalDiagnostics")
    require(isinstance(summary, dict) and isinstance(issues, list),
            "PYRIGHT_INSTALLED_CONSUMER_DIAGNOSTICS_MISSING")
    require(all(isinstance(x, dict) for x in issues),
            "PYRIGHT_INSTALLED_CONSUMER_DIAGNOSTICS_MALFORMED")
    errors = [x for x in issues if x.get("severity") == "error"]
    require(summary.get("errorCount") == len(errors),
            "PYRIGHT_INSTALLED_CONSUMER_ERROR_COUNT_DRIFT")
    if negative:
        observed = [x.get("rule") for x in errors]
        require(completed.returncode == 1 and len(errors) >= 4
                and observed.count("reportArgumentType") >= 3
                and "reportAssignmentType" in observed,
                "PYRIGHT_INSTALLED_CONSUMER_NEGATIVE_CONTROLS_MISSING")
    else:
        require(completed.returncode == 0 and not errors,
                "PYRIGHT_INSTALLED_CONSUMER_POSITIVE_REJECTED")
    require(all(Path(str(x.get("file", ""))).name == "consumer.py" for x in errors),
            "PYRIGHT_INSTALLED_CONSUMER_DIAGNOSTIC_OUT_OF_SCOPE")
    raw = completed.stdout.encode("utf-8")
    return {
        "fixture": source.name,
        "fixture_sha256": sha256(source.read_bytes()).hexdigest(),
        "project_config_sha256": sha256(
            (project / "pyrightconfig.json").read_bytes()).hexdigest(),
        "native_json_sha256": sha256(raw).hexdigest(),
        "native_error_count": len(errors),
        "native_error_rules": sorted(str(x.get("rule")) for x in errors),
        "status": "EXPECTED_NEGATIVE_DIAGNOSTICS" if negative else "TYPE_NO_ERRORS",
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--pyright", type=Path, required=True)
    p.add_argument("--venv", type=Path, required=True)
    p.add_argument("--positive", type=Path, required=True)
    p.add_argument("--negative", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    require(version("pyright") == PYRIGHT, "PYRIGHT_INSTALLED_CONSUMER_NOT_PINNED")
    require(version("codeqa") == "0.2.0a1", "CODEQA_INSTALLED_CONSUMER_VERSION_DRIFT")
    import codeqa
    require(Path(codeqa.__file__).resolve().is_relative_to(args.venv.resolve()),
            "PYRIGHT_INSTALLED_CONSUMER_IMPORTED_CHECKOUT_SOURCE")
    with TemporaryDirectory(prefix="codeqa-installed-typecheck-") as tmp:
        root = Path(tmp)
        positive = run_typecheck(args.pyright, args.venv, args.positive,
                                 root / "positive", negative=False)
        negative = run_typecheck(args.pyright, args.venv, args.negative,
                                 root / "negative", negative=True)
    receipt = {
        "schema_version": "0.1",
        "python": f"{sys.version_info.major}.{sys.version_info.minor}",
        "pyright": PYRIGHT,
        "codeqa": version("codeqa"),
        "consumer": "CONTROLLED_INSTALLED_WHEEL_SOURCE_ONLY",
        "external_public_sdk_consumer": "NOT_EVALUATED",
        "production_abi_and_database": "NOT_EVALUATED",
        "positive": positive,
        "negative": negative,
    }
    args.output.write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n",
                           encoding="utf-8")
    print("INSTALLED_PYRIGHT=PASS positive=TYPE_NO_ERRORS negative=REJECTED "
          "public_consumer=NOT_EVALUATED")


if __name__ == "__main__":
    main()
