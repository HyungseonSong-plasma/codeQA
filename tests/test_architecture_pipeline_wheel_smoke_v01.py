"""#184: validate known Pipeline imports from a built, installed wheel.

This is a bounded distribution smoke test, not an external-consumer survey,
a semantic ownership verdict, or authorization to relocate public modules.
An import-line trace observes execution of a source line, not each alias binding,
semantic ownership, or safety of a future move.
The isolated interpreter must import codeQA from the wheel installation,
not from the checkout's editable install.
"""
from __future__ import annotations

import ast
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


def _module_source_path(module_name: str) -> Path:
    """Resolve an observed in-repository import to exactly one source file."""
    relative = Path(*module_name.split("."))
    candidates = (
        ROOT / "src" / relative.with_suffix(".py"),
        ROOT / "src" / relative / "__init__.py",
    )
    existing = [path for path in candidates if path.is_file()]
    if len(existing) != 1:
        raise AssertionError(
            f"expected exactly one source file for {module_name}: {existing}"
        )
    return existing[0]


def _cross_role_pipeline_imports():
    """Enumerate all literal cross-role imports in current Pipeline sources.

    This is source-syntax evidence, not a claim that each import statement ran,
    that imported objects are semantically owned, or that external callers work.
    The census is deliberately derived from the checkout, not a fixed list of
    Naming/Adapter hypotheses or a hard-coded historical pair count.
    """
    records = []
    for path in sorted((ROOT / "src/codeqa/pipeline").glob("*.py")):
        raw = path.read_bytes()
        importer_module = ".".join(
            path.relative_to(ROOT / "src").with_suffix("").parts
        )
        for node in ast.walk(ast.parse(raw.decode("utf-8"), filename=str(path))):
            if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                candidates = [(node.module, [alias.name for alias in node.names])]
            elif isinstance(node, ast.Import):
                candidates = [(alias.name, []) for alias in node.names]
            else:
                continue
            for module_name, symbols in candidates:
                parts = module_name.split(".")
                if (len(parts) < 2 or parts[0] != "codeqa"
                        or parts[1] not in (
                            "adapters", "core", "evaluation", "infrastructure"
                        )):
                    continue
                target_source = _module_source_path(module_name)
                records.append({
                    "target_source_relative": target_source.relative_to(
                        ROOT / "src"
                    ).as_posix(),
                    "target_sha256": sha256(target_source.read_bytes()).hexdigest(),
                    "importer_module": importer_module,
                    "importer_sha256": sha256(raw).hexdigest(),
                    "line": node.lineno,
                    "module": module_name,
                    "symbols": symbols,
                    "target_role": parts[1],
                })
    return sorted(records, key=lambda row: (
        row["importer_module"], row["line"], row["module"],
    ))


class PipelineWheelSmokeTests(unittest.TestCase):
    def test_installed_wheel_preserves_known_pipeline_import_surface(self):
        with tempfile.TemporaryDirectory(prefix="codeqa-wheel-smoke-") as tmp:
            scratch = Path(tmp)
            wheel_dir = scratch / "wheels"
            wheel_dir.mkdir()
            installed = scratch / "installed"

            # Build isolation obtains the declared setuptools backend from
            # pyproject.toml. Python 3.12 runners need not preinstall it.
            # Runtime dependencies are not resolved by this wheel build.
            build = subprocess.run(
                [
                    sys.executable, "-m", "pip", "wheel",
                    "--no-deps", "--no-cache-dir",
                    "--wheel-dir", str(wheel_dir), str(ROOT),
                ],
                cwd=scratch, capture_output=True, text=True, timeout=120,
                check=False,
            )
            self.assertEqual(
                build.returncode, 0,
                f"wheel build failed:\n{build.stdout}\n{build.stderr}",
            )
            wheels = sorted(wheel_dir.glob("codeqa-*.whl"))
            self.assertEqual(len(wheels), 1, "expected one built codeQA wheel")

            install = subprocess.run(
                [
                    sys.executable, "-m", "pip", "install", "--no-index",
                    "--no-deps", "--no-compile", "--target", str(installed),
                    str(wheels[0]),
                ],
                cwd=scratch, capture_output=True, text=True, timeout=120,
                check=False,
            )
            self.assertEqual(
                install.returncode, 0,
                f"wheel install failed:\n{install.stdout}\n{install.stderr}",
            )

            # Check behavior against the same source/profile on the checkout.
            # This is a bounded regression, not external-consumer certification.
            from codeqa.infrastructure.resources import ResourceRegistry
            from codeqa.pipeline.python import analyze_python as checkout_analyze

            registry = ResourceRegistry(ROOT)
            ccg_schema = registry.load_json("ccg_schema")
            mechanical_profile = registry.load_json("mechanical_profile")
            cases = [
                {
                    "src/pkg/a.py": "def helper():\n    return 1\n",
                    "src/pkg/b.py": (
                        "from pkg.a import helper\n\ndef run():\n"
                        "    return helper()\n"
                    ),
                },
                {
                    "src/pkg/a.py": "def helper():\n    return 1\n",
                    "src/pkg/b.py": "def broken(",
                },
            ]
            expected = [
                checkout_analyze(
                    sources, snapshot_id="git:wheel-behavior-v01",
                    ccg_schema=ccg_schema, mechanical_profile=mechanical_profile,
                ).to_document()
                for sources in cases
            ]
            self.assertEqual(expected[0]["summary"]["source"]["coverage"], "complete")
            self.assertEqual(expected[1]["summary"]["source"]["coverage"], "partial")
            payload = {
                "cases": cases, "ccg_schema": ccg_schema,
                "mechanical_profile": mechanical_profile,
            }
            cross_role_imports = _cross_role_pipeline_imports()
            self.assertTrue(cross_role_imports, "no source-derived cross-role imports")
            self.assertEqual(
                len({(r["importer_module"], r["module"])
                     for r in cross_role_imports}), len(cross_role_imports),
                "expected one measured source/target module pair per record",
            )
            payload["pipeline_cross_role_imports"] = cross_role_imports
            expected_digest = sha256(json.dumps(
                expected, sort_keys=True, separators=(",", ":"),
            ).encode()).hexdigest()

            # -I excludes PYTHONPATH and the current directory; the target
            # installation is prepended explicitly and its origin asserted.
            consumer = r"""
import importlib
import importlib.util
import inspect
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import sys

target = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(target))

# Trace original import statement lines in the isolated interpreter, before
# any codeqa package import can populate sys.modules. This is a line-level
# execution witness only; it cannot attribute individual aliases or semantics.
payload = json.loads(sys.stdin.read())
cross_role_imports = payload["pipeline_cross_role_imports"]
candidate_import_lines = {
    (record["importer_module"], record["line"])
    for record in cross_role_imports
}
negative_trace_control = ("codeqa.pipeline.python", 10**9)
candidate_import_lines.add(negative_trace_control)
observed_import_lines = set()

def trace_import_lines(frame, event, arg):
    if event == "line":
        key = (frame.f_globals.get("__name__"), frame.f_lineno)
        if key in candidate_import_lines:
            observed_import_lines.add(key)
    return trace_import_lines

sys.settrace(trace_import_lines)

import codeqa
import codeqa.pipeline as pipeline
import codeqa.pipeline.python as python_pipeline
from codeqa.pipeline.analysis_request import analyze_python_request

for module in (codeqa, pipeline, python_pipeline):
    assert Path(module.__file__).resolve().is_relative_to(target), module.__file__
assert pipeline.PythonAnalysis is python_pipeline.PythonAnalysis
assert pipeline.analyze_python is python_pipeline.analyze_python
assert set(pipeline.__all__) == {"PythonAnalysis", "analyze_python"}
inspect.signature(pipeline.analyze_python).bind(
    {}, snapshot_id="git:wheel-smoke", ccg_schema={}, mechanical_profile={}
)
inspect.signature(analyze_python_request).bind(object())
assert importlib.util.find_spec(
    "codeqa.pipeline.__definitely_missing_module__"
) is None
# Exercise every source-derived Pipeline importer and its declared target
# module/symbol in the isolated installed wheel. This proves bounded import
# resolution, not execution of each original import statement or safe migration.
cross_role_imports = payload["pipeline_cross_role_imports"]
for record in cross_role_imports:
    importer = importlib.import_module(record["importer_module"])
    importer_path = Path(importer.__file__).resolve()
    assert importer_path.is_relative_to(target), importer_path
    assert sha256(importer_path.read_bytes()).hexdigest() == record["importer_sha256"]
    imported = importlib.import_module(record["module"])
    imported_path = Path(imported.__file__).resolve()
    assert imported_path.is_relative_to(target), imported.__file__
    assert imported_path.relative_to(target).as_posix() == record["target_source_relative"]
    assert sha256(imported_path.read_bytes()).hexdigest() == record["target_sha256"], (
        "target module SHA mismatch: " + record["module"]
    )
    for symbol in record["symbols"]:
        assert symbol != "*", "star imports require separate review"
        if not hasattr(imported, symbol):
            child = importlib.import_module(record["module"] + "." + symbol)
            assert Path(child.__file__).resolve().is_relative_to(target), child.__file__

documents = [
    pipeline.analyze_python(
        sources, snapshot_id="git:wheel-behavior-v01",
        ccg_schema=payload["ccg_schema"],
        mechanical_profile=payload["mechanical_profile"],
    ).to_document()
    for sources in payload["cases"]
]
sys.settrace(None)
assert negative_trace_control not in observed_import_lines
import_line_observations = [{
    "importer_module": record["importer_module"],
    "module": record["module"],
    "line": record["line"],
    "importer_sha256": record["importer_sha256"],
    "import_line_observed": (
        record["importer_module"], record["line"]
    ) in observed_import_lines,
} for record in cross_role_imports]
print(json.dumps({
    "document_digest": sha256(json.dumps(
        documents, sort_keys=True, separators=(",", ":"),
    ).encode()).hexdigest(),
    "cross_role_pairs": len(cross_role_imports),
    "import_line_observations": import_line_observations,
    "observed_import_line_pairs": sum(
        row["import_line_observed"] for row in import_line_observations
    ),
    "target_roles": dict(sorted(Counter(
        record["target_role"] for record in cross_role_imports
    ).items())),
}, sort_keys=True))
"""
            result = subprocess.run(
                [sys.executable, "-I", "-c", consumer, str(installed)],
                cwd=scratch, capture_output=True, text=True, timeout=60,
                input=json.dumps(payload), check=False,
            )
            self.assertEqual(
                result.returncode, 0,
                f"isolated installed-wheel consumer failed:\n"
                f"{result.stdout}\n{result.stderr}",
            )
            receipt = json.loads(result.stdout)
            self.assertEqual(receipt["document_digest"], expected_digest,
                             "installed wheel changed the known Pipeline analysis document")
            self.assertEqual(receipt["cross_role_pairs"], len(cross_role_imports))
            self.assertEqual(receipt["target_roles"], dict(sorted(Counter(
                row["target_role"] for row in cross_role_imports
            ).items())))

            # This is source-line traversal, not proof that every target alias
            # was bound or that unobserved statements are dead code.
            observations = receipt["import_line_observations"]
            self.assertEqual(
                [(row["importer_module"], row["module"], row["line"],
                  row["importer_sha256"]) for row in observations],
                [(row["importer_module"], row["module"], row["line"],
                  row["importer_sha256"]) for row in cross_role_imports],
            )
            self.assertTrue(all(
                type(row["import_line_observed"]) is bool for row in observations
            ))
            self.assertEqual(
                receipt["observed_import_line_pairs"],
                sum(row["import_line_observed"] for row in observations),
            )
            self.assertGreater(
                receipt["observed_import_line_pairs"], 0,
                "isolated interpreter did not trace any known import statement",
            )
            print("pipeline_wheel_import_line_trace=" + json.dumps({
                "observed_import_line_pairs": receipt["observed_import_line_pairs"],
                "total_cross_role_pairs": len(cross_role_imports),
                "unobserved_import_line_pairs": (
                    len(cross_role_imports) - receipt["observed_import_line_pairs"]
                ),
                "evidence_limit": "LINE_EXECUTION_ONLY_NOT_SEMANTIC_OWNERSHIP",
            }, sort_keys=True))

            # Negative control: a wheel whose target module bytes differ from
            # the pinned checkout must fail, even when its imports still work.
            target_source = installed / cross_role_imports[0]["target_source_relative"]
            target_source.write_bytes(
                target_source.read_bytes() + b"\n# deliberate wheel byte drift\n"
            )
            tampered = subprocess.run(
                [sys.executable, "-I", "-c", consumer, str(installed)],
                cwd=scratch, capture_output=True, text=True, timeout=60,
                input=json.dumps(payload), check=False,
            )
            self.assertNotEqual(tampered.returncode, 0)
            self.assertIn("target module SHA mismatch", tampered.stderr)


if __name__ == "__main__":
    unittest.main()
