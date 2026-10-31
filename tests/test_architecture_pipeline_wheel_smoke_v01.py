"""#184: validate known Pipeline imports from a built, installed wheel.

This is a bounded distribution smoke test, not an external-consumer survey,
a semantic ownership verdict, or authorization to relocate public modules.
The isolated interpreter must import codeQA from the wheel installation,
not from the checkout's editable install.
"""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


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
            expected_digest = sha256(json.dumps(
                expected, sort_keys=True, separators=(",", ":"),
            ).encode()).hexdigest()

            # -I excludes PYTHONPATH and the current directory; the target
            # installation is prepended explicitly and its origin asserted.
            consumer = r"""
import importlib.util
import inspect
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
documents = [
    pipeline.analyze_python(
        sources, snapshot_id="git:wheel-behavior-v01",
        ccg_schema=payload["ccg_schema"],
        mechanical_profile=payload["mechanical_profile"],
    ).to_document()
    for sources in payload["cases"]
]
print(sha256(json.dumps(
    documents, sort_keys=True, separators=(",", ":"),
).encode()).hexdigest())
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
            self.assertEqual(result.stdout.strip(), expected_digest,
                             "installed wheel changed the known Pipeline analysis document")


if __name__ == "__main__":
    unittest.main()
