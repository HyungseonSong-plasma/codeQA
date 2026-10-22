"""Positive and adversarial Ground Truth for behavior syntax versus responsibility."""
from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import unittest

from jsonschema import Draft202012Validator
from codeqa.infrastructure.resources import ResourceRegistry
from codeqa.pipeline.python import analyze_python
from codeqa.evaluation.responsibility_behavior import (
    evaluate_responsibility_behavior, validate_behavior_policy,
)

ROOT = Path(__file__).resolve().parents[1]


def roles():
    return {
        "scope": "src/pkg", "policy_id": "fixture.roles",
        "roles": {
            "adapters": {"responsibility": "source parsing", "forbidden_imports": []},
            "evaluation": {"responsibility": "pure evaluation", "forbidden_imports": []},
            "core": {"responsibility": "immutable models", "forbidden_imports": []},
        },
        "exceptions": [],
    }


def behavior():
    return {
        "scope": "src/pkg", "policy_id": "fixture.behavior", "schema_version": "0.1",
        "catalog": [
            {"module": "ast", "symbol": "walk",
             "kind": "AST_SOURCE_INTERPRETATION_SYNTAX"},
            {"module": "ast", "symbol": "parse",
             "kind": "AST_SOURCE_INTERPRETATION_SYNTAX"},
            {"module": "subprocess", "symbol": "run",
             "kind": "PROCESS_INVOCATION_SYNTAX"},
        ],
        "roles": {
            "adapters": {"forbidden": ["PROCESS_INVOCATION_SYNTAX"]},
            "evaluation": {"forbidden": ["AST_SOURCE_INTERPRETATION_SYNTAX",
                                         "PROCESS_INVOCATION_SYNTAX"]},
            "core": {"forbidden": ["AST_SOURCE_INTERPRETATION_SYNTAX",
                                   "PROCESS_INVOCATION_SYNTAX"]},
        },
    }


class BehaviorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        registry = ResourceRegistry(ROOT)
        cls.ccg = registry.load_json("ccg_schema")
        cls.mechanical = registry.load_json("mechanical_profile")
        cls.report_schema = json.loads(
            (ROOT / "contracts/semantic/responsibility-behavior-v0.1.schema.json").read_text()
        )

    def analyze(self, sources, role_policy=None, behavior_policy=None):
        return analyze_python(
            sources, snapshot_id="fixed-snapshot",
            ccg_schema=self.ccg, mechanical_profile=self.mechanical,
            semantic_policy=roles() if role_policy is None else role_policy,
            behavior_policy=behavior() if behavior_policy is None else behavior_policy,
        )

    def test_ast_call_is_source_observation_and_role_compatible_not_pass(self):
        a = self.analyze({
            "src/pkg/adapters/a.py": "import ast as syntax\n"
                                      "def extract(text):\n    return syntax.parse(text)\n",
            "src/pkg/evaluation/e.py": "def evaluate(x): return x\n",
            "src/pkg/core/m.py": "VALUE = 1\n",
        })
        report = a.responsibility_behavior
        self.assertEqual(report.status, "NOT_EVALUATED")
        self.assertEqual(len(report.observations), 1)
        obs = report.observations[0]
        self.assertEqual(obs.declared_module, "ast")
        self.assertEqual(obs.declared_symbol, "parse")
        self.assertEqual(obs.behavior_kind, "AST_SOURCE_INTERPRETATION_SYNTAX")
        self.assertEqual(obs.assurance, "DECLARED_API_CALL_SYNTAX_ONLY")
        self.assertEqual(obs.source_node_id, "def::src/pkg/adapters/a.py::extract@2:0")
        self.assertIn(obs.evidence_id, {f.evidence_id for f in a.evidence.facts})
        self.assertEqual(report.placements[0].status, "ROLE_COMPATIBLE_OBSERVATION")
        self.assertIn("NOT_EVALUATED", report.summary_document()["status"])

    def test_same_signature_in_wrong_role_is_review_not_verified_violation(self):
        a = self.analyze({
            "src/pkg/evaluation/e.py": "import ast\n"
                                      "def evaluate(tree):\n    return ast.walk(tree)\n",
            "src/pkg/adapters/a.py": "pass\n",
            "src/pkg/core/m.py": "pass\n",
        })
        report = a.responsibility_behavior
        self.assertEqual(report.status, "REVIEW_REQUIRED")
        self.assertEqual(report.placements[0].status, "ROLE_CONFLICT_REVIEW")
        self.assertEqual(report.placements[0].directory_role, "evaluation")
        self.assertEqual(a.semantic_architecture.status, "NOT_EVALUATED")
        self.assertEqual(a.quality.status, "PASS")

    def test_from_import_alias_is_grounded(self):
        a = self.analyze({
            "src/pkg/evaluation/e.py": "from subprocess import run as launch\n"
                                      "def evaluate():\n    return launch(['x'])\n",
            "src/pkg/adapters/a.py": "pass\n",
            "src/pkg/core/m.py": "pass\n",
        })
        obs = a.responsibility_behavior.observations[0]
        self.assertEqual((obs.declared_module, obs.declared_symbol),
                         ("subprocess", "run"))
        self.assertEqual(obs.expression, "launch")
        self.assertEqual(a.responsibility_behavior.status, "REVIEW_REQUIRED")

    def test_module_rebinding_suppresses_identity_inference(self):
        a = self.analyze({
            "src/pkg/adapters/a.py": "import ast\nast = Fake()\n"
                                      "def f(x):\n    return ast.parse(x)\n",
            "src/pkg/evaluation/e.py": "", "src/pkg/core/m.py": "",
        })
        self.assertEqual(a.responsibility_behavior.observations, ())

    def test_parameter_shadowing_and_local_binding_suppress_observation(self):
        a = self.analyze({
            "src/pkg/adapters/a.py": "import ast\n"
                                      "def f(ast):\n    return ast.walk(1)\n"
                                      "def g():\n    ast = Fake()\n    return ast.parse('a')\n",
            "src/pkg/evaluation/e.py": "", "src/pkg/core/m.py": "",
        })
        self.assertEqual(a.responsibility_behavior.observations, ())

    def test_unknown_fluid_methods_are_not_guessed_behavior(self):
        a = self.analyze({
            "src/pkg/evaluation/e.py":
                "def evaluate(x):\n    return x.walk().parse()\n",
            "src/pkg/adapters/a.py": "", "src/pkg/core/m.py": "",
        })
        self.assertEqual(a.responsibility_behavior.observations, ())
        self.assertEqual(a.responsibility_behavior.status, "NOT_EVALUATED")

    def test_dotted_import_without_alias_is_not_assumed_bound_module(self):
        a = self.analyze({
            "src/pkg/evaluation/e.py":
                "import ast.helpers\n"
                "def evaluate(t):\n    return ast.walk(t)\n",
            "src/pkg/adapters/a.py": "", "src/pkg/core/m.py": "",
        })
        self.assertEqual(a.responsibility_behavior.observations, ())

    def test_nested_function_attribution_not_to_parent_and_lambda_skipped(self):
        a = self.analyze({
            "src/pkg/adapters/a.py": "import ast\n"
               "def outer():\n"
               "    def inner():\n"
               "        return ast.parse('1')\n"
               "    f = lambda: ast.walk(1)\n"
               "    return inner()\n",
            "src/pkg/evaluation/e.py": "", "src/pkg/core/m.py": "",
        })
        report = a.responsibility_behavior
        self.assertEqual(len(report.observations), 1)
        self.assertIn("::outer.inner@", report.observations[0].source_node_id)

    def test_duplicate_import_alias_is_unknown(self):
        a = self.analyze({
            "src/pkg/adapters/a.py": "import ast as api\nimport subprocess as api\n"
                                      "def f(x): return api.run(x)\n",
            "src/pkg/evaluation/e.py": "", "src/pkg/core/m.py": "",
        })
        self.assertEqual(a.responsibility_behavior.observations, ())

    def test_policy_validation_rejects_scope_and_duplicate_catalog(self):
        p = behavior()
        bad = dict(p)
        bad["scope"] = "other"
        with self.assertRaises(ValueError):
            validate_behavior_policy(bad, roles())
        bad = dict(p)
        bad["catalog"] = [p["catalog"][0], p["catalog"][0]]
        with self.assertRaises(ValueError):
            validate_behavior_policy(bad, roles())
        bad = dict(p)
        bad["roles"] = {"adapters": {"forbidden": []}}
        with self.assertRaises(ValueError):
            validate_behavior_policy(bad, roles())

    def test_behavior_policy_requires_declared_directory_roles(self):
        src = {"src/pkg/adapters/a.py": "import ast\n"}
        with self.assertRaises(ValueError):
            analyze_python(src, snapshot_id="fixed-snapshot",
                ccg_schema=self.ccg, mechanical_profile=self.mechanical,
                behavior_policy=behavior())

    def test_report_serialization_and_determinism(self):
        src = {
            "src/pkg/adapters/a.py": "import ast\n"
                                      "def f(t): return ast.parse(t)\n",
            "src/pkg/evaluation/e.py": "import subprocess\n"
                                         "def g(): return subprocess.run(['x'])\n",
            "src/pkg/core/m.py": "",
        }
        first = self.analyze(src).responsibility_behavior
        second = self.analyze(dict(reversed(list(src.items())))).responsibility_behavior
        self.assertEqual(first, second)
        Draft202012Validator.check_schema(self.report_schema)
        Draft202012Validator(self.report_schema).validate(first.to_document())
        self.assertEqual(
            first.summary_document()["placements_by_status"],
            {"ROLE_COMPATIBLE_OBSERVATION": 1, "ROLE_CONFLICT_REVIEW": 1},
        )

    def test_legacy_reports_unchanged_with_optional_behavior_analysis(self):
        src = {
            "src/pkg/adapters/a.py": "import ast\n"
                                      "def f(x): return ast.parse(x)\n",
            "src/pkg/evaluation/e.py": "",
            "src/pkg/core/m.py": "",
        }
        base = analyze_python(src, snapshot_id="fixed-snapshot",
            ccg_schema=self.ccg, mechanical_profile=self.mechanical,
            semantic_policy=roles())
        extra = self.analyze(src)
        self.assertIsNone(base.responsibility_behavior)
        self.assertEqual(base.summary_document()["responsibility_behavior"]["status"],
                         "NOT_REQUESTED")
        for attr in ("graph", "quality", "dependencies", "evidence",
                     "function_context", "contextual_review", "symbol_calls",
                     "semantic_architecture"):
            self.assertEqual(getattr(base, attr), getattr(extra, attr))

    def test_manual_synthetic_observation_stays_review_not_runtime_violation(self):
        a = self.analyze({
            "src/pkg/adapters/a.py": "", "src/pkg/evaluation/e.py": "",
            "src/pkg/core/m.py": "",
        })
        from codeqa.core.behavior import BehaviorObservation
        invented = BehaviorObservation(
            "def::src/pkg/core/m.py::f@1:0", "src/pkg/core/m.py",
            2, 4, "ast.parse", "ast", "parse",
            "AST_SOURCE_INTERPRETATION_SYNTAX", "synthetic-id",
        )
        report = evaluate_responsibility_behavior(
            (invented,), snapshot_id=a.graph.snapshot.id,
            scanned_call_sites=1, excluded_by_reason=(),
            role_policy=roles(), behavior_policy=behavior(),
        )
        self.assertEqual(report.status, "REVIEW_REQUIRED")
        self.assertNotIn("VIOLATION", report.to_document()["status"])


if __name__ == "__main__":
    unittest.main()
