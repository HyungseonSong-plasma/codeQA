"""#39: declared role-policy v0.1, existing authority and source witnesses."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import unittest

from jsonschema import Draft202012Validator, FormatChecker

from codeqa.evaluation.architecture_rules import (
    DeclaredRuleError, evaluate_declared_architecture_rules,
    validate_declared_rule_policy,
)
from codeqa.evaluation.semantic_layout import evaluate_semantic_layout
from codeqa.infrastructure.resources import ResourceRegistry
from codeqa.pipeline.python import analyze_python


ROOT = Path(__file__).resolve().parents[1]


def policy() -> dict:
    return {
        "schema_version": "0.1", "policy_id": "fixture.policy",
        "revision": "2026-10-23", "scope": "src/pkg",
        "effective_from": "2026-01-01", "temporality": "CONTEMPORANEOUS",
        "scope_inventory_complete": True,
        "roles": {
            "core": {
                "responsibility": "source and immutable facts",
                "allowed_imports": ["core"], "forbidden_imports": ["api"],
            },
            "api": {
                "responsibility": "entry points",
                "allowed_imports": ["api", "core"], "forbidden_imports": [],
            },
        },
        "exceptions": [],
    }


class DeclaredArchitectureRulesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        registry = ResourceRegistry(ROOT)
        cls.ccg_schema = registry.load_json("ccg_schema")
        cls.mechanical_profile = registry.load_json("mechanical_profile")
        cls.schema = json.loads(
            (ROOT / "contracts/semantic/declared-rule-policy-v0.1.schema.json").read_text()
        )
        cls.report_schema = json.loads(
            (ROOT / "contracts/semantic/declared-rule-report-v0.1.schema.json").read_text()
        )
        Draft202012Validator.check_schema(cls.schema)
        Draft202012Validator.check_schema(cls.report_schema)

    def analyze(self, sources, declared=None, *, day="2026-10-23"):
        result = analyze_python(
            sources, snapshot_id="sha:pinned-A",
            ccg_schema=self.ccg_schema,
            mechanical_profile=self.mechanical_profile,
        )
        report = evaluate_declared_architecture_rules(
            result.graph, result.dependencies, policy() if declared is None else declared,
            schema=self.schema, source_as_of=day,
        )
        Draft202012Validator(self.report_schema, format_checker=FormatChecker()).validate(
            report.to_document()
        )
        return result, report

    def test_exact_from_import_boundary_violation_has_line_rule_and_clause(self):
        sources = {
            "src/pkg/core/mod.py": "from pkg.api import entry\n",
            "src/pkg/api/__init__.py": "entry = 1\n",
        }
        result, report = self.analyze(sources)
        violations = [f for f in report.findings if f.status == "VIOLATION"]
        self.assertEqual(len(violations), 1)
        f = violations[0]
        self.assertEqual(f.rule_id, "direction:core->api")
        self.assertEqual(f.policy_clause, "roles.core.forbidden_imports")
        self.assertEqual((f.source, f.target, f.line), (
            "src/pkg/core/mod.py", "src/pkg/api/__init__.py", 1
        ))
        self.assertIn("from pkg.api import entry", f.expression)
        self.assertEqual(f.execution, "top_level")
        self.assertEqual(report.status, "VIOLATION")
        raw_policy = policy()
        previous = evaluate_semantic_layout(
            result.graph.coverage.analyzed_paths,
            [(e.source_path, e.target_path) for e in result.dependencies.edges],
            {
                "policy_id": raw_policy["policy_id"],
                "scope": raw_policy["scope"],
                "roles": {
                    k: {"responsibility": v["responsibility"],
                        "forbidden_imports": v["forbidden_imports"]}
                    for k, v in raw_policy["roles"].items()
                },
                "exceptions": [],
            },
        )
        self.assertEqual(previous.findings[0].code, f.code)
        self.assertEqual(previous.status, report.status)

    def test_conditional_static_edge_does_not_claim_runtime_execution(self):
        _, report = self.analyze({
            "src/pkg/core/mod.py": "if flag:\n    import pkg.api\n",
            "src/pkg/api/__init__.py": "",
        })
        finding = next(f for f in report.findings if f.code == "FORBIDDEN_ROLE_DEPENDENCY")
        self.assertEqual(finding.line, 2)
        self.assertEqual(finding.execution, "conditional_or_deferred")
        self.assertIn("NOT_P4_P5_CERTIFICATION", report.interpretation)

    def test_named_active_exception_is_review_not_clear(self):
        doc = policy()
        doc["exceptions"] = [{
            "id": "TEMP-1", "source": "src/pkg/core/mod.py",
            "target": "src/pkg/api/__init__.py",
            "rationale": "legacy migration", "expires_on": "2026-11-01",
        }]
        _, report = self.analyze({
            "src/pkg/core/mod.py": "import pkg.api\n",
            "src/pkg/api/__init__.py": "",
        }, doc)
        self.assertEqual(report.status, "REVIEW_REQUIRED")
        review = next(f for f in report.findings if f.code == "DECLARED_TRANSITIONAL_EDGE")
        self.assertEqual(review.exception_id, "TEMP-1")
        self.assertEqual(review.line, 1)

    def test_expired_exception_no_longer_suppresses_forbidden_edge(self):
        doc = policy()
        doc["exceptions"] = [{
            "id": "OLD-1", "source": "src/pkg/core/mod.py",
            "target": "src/pkg/api/__init__.py",
            "rationale": "migration expired", "expires_on": "2026-02-01",
        }]
        _, report = self.analyze({
            "src/pkg/core/mod.py": "import pkg.api\n",
            "src/pkg/api/__init__.py": "",
        }, doc)
        self.assertEqual(report.status, "VIOLATION")
        self.assertIn("EXPIRED_EXCEPTION", {f.code for f in report.findings})
        self.assertIn("FORBIDDEN_ROLE_DEPENDENCY", {f.code for f in report.findings})

    def test_incomplete_inventory_cannot_prove_role_absence(self):
        doc = policy()
        doc["scope_inventory_complete"] = False
        _, report = self.analyze({"src/pkg/core/mod.py": "pass\n"}, doc)
        self.assertEqual(report.status, "NOT_EVALUATED")
        self.assertIn("ROLE_ABSENCE_UNPROVEN", {f.code for f in report.findings})
        self.assertFalse(any(f.code == "MISSING_DECLARED_ROLE" for f in report.findings))
        _, complete = self.analyze({"src/pkg/core/mod.py": "pass\n"})
        self.assertIn("MISSING_DECLARED_ROLE", {f.code for f in complete.findings})

    def test_unmapped_dynamic_import_and_partial_parse_fail_closed(self):
        sources = {
            "src/pkg/core/mod.py": "import external_package\n__import__('pkg.api')\n",
            "src/pkg/api/__init__.py": "entry = 1\n",
        }
        _, report = self.analyze(sources)
        self.assertIn("UNKNOWN_STATIC_IMPORT_TARGET", {f.code for f in report.findings})
        self.assertEqual(report.status, "NOT_EVALUATED")
        sources["src/pkg/api/__init__.py"] = "def ("
        _, partial = self.analyze(sources)
        self.assertEqual(partial.coverage_status, "partial")
        self.assertEqual(partial.status, "NOT_EVALUATED")
        self.assertIn("PARTIAL_SOURCE_COVERAGE", {f.code for f in partial.findings})
        self.assertFalse(any(f.status == "VIOLATION" for f in partial.findings))

    def test_retrospective_or_future_policy_does_not_fabricate_violation(self):
        sources = {
            "src/pkg/core/mod.py": "import pkg.api\n",
            "src/pkg/api/__init__.py": "",
        }
        r = policy()
        r["temporality"] = "RETROSPECTIVE"
        self.assertEqual(self.analyze(sources, r)[1].status, "NOT_EVALUATED")
        r["temporality"] = "CONTEMPORANEOUS"
        self.assertEqual(self.analyze(sources, r, day="2025-12-31")[1].status,
                         "NOT_EVALUATED")

    def test_rule_direction_conflicts_unsafe_paths_and_dates_fail_closed(self):
        for mutation in ("overlap", "unknown", "bad_date", "bad_revision",
                         "invalid_scope", "duplicate_exceptions", "expired_before_active"):
            with self.subTest(mutation=mutation):
                p = policy()
                if mutation == "overlap":
                    p["roles"]["core"]["allowed_imports"].append("api")
                elif mutation == "unknown":
                    p["roles"]["core"]["forbidden_imports"] = ["unknown"]
                elif mutation == "bad_date":
                    p["effective_from"] = "2026-99-99"
                elif mutation == "bad_revision":
                    del p["revision"]
                elif mutation == "invalid_scope":
                    p["scope"] = "../src/pkg"
                else:
                    entry = {
                        "id": "E-1", "source": "src/pkg/core/mod.py",
                        "target": "src/pkg/api/__init__.py",
                        "rationale": "temporary", "expires_on": "2026-10-29",
                    }
                    p["exceptions"] = [entry]
                    if mutation == "duplicate_exceptions":
                        p["exceptions"].append(deepcopy(entry))
                    else:
                        p["exceptions"][0]["expires_on"] = "2025-01-01"
                with self.assertRaises(DeclaredRuleError):
                    validate_declared_rule_policy(p, self.schema)

    def test_snapshot_or_dependency_coverage_mismatch_is_rejected(self):
        analysis = analyze_python({
            "src/pkg/core/mod.py": "pass\n",
            "src/pkg/api/__init__.py": "",
        }, snapshot_id="sha:pinned-A", ccg_schema=self.ccg_schema,
            mechanical_profile=self.mechanical_profile)
        for bad in (
            replace(analysis.dependencies, snapshot_id="different"),
            replace(analysis.dependencies, unprocessed_paths=("ghost.py",)),
        ):
            with self.subTest(bad=bad), self.assertRaises(DeclaredRuleError):
                evaluate_declared_architecture_rules(
                    analysis.graph, bad, policy(),
                    schema=self.schema, source_as_of="2026-10-23",
                )

    def test_determinism_and_existing_mechanical_not_mutated(self):
        sources = {
            "src/pkg/api/__init__.py": "",
            "src/pkg/core/mod.py": "from pkg.api import entry\n",
        }
        a, first = self.analyze(sources)
        b, second = self.analyze(dict(reversed(list(sources.items()))))
        self.assertEqual(first.to_document(), second.to_document())
        self.assertEqual(a.quality, b.quality)
        self.assertEqual(a.graph, b.graph)
        self.assertNotIn("declared_rules", a.to_document())


if __name__ == "__main__":
    unittest.main()
