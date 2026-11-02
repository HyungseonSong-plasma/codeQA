"""#184: validate known Pipeline imports from a built, installed wheel.

This is a bounded distribution smoke test, not an external-consumer survey,
a semantic ownership verdict, or authorization to relocate public modules.
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
                records.append({
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
payload = json.loads(sys.stdin.read())

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
    assert Path(imported.__file__).resolve().is_relative_to(target), imported.__file__
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
print(json.dumps({
    "document_digest": sha256(json.dumps(
        documents, sort_keys=True, separators=(",", ":"),
    ).encode()).hexdigest(),
    "cross_role_pairs": len(cross_role_imports),
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


if __name__ == "__main__":
    unittest.main()
