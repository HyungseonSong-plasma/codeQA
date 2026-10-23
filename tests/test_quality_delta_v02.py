"""#40: grounded per-rule QA Delta v0.2, migration and fail-closed controls."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import unittest

from jsonschema import Draft202012Validator

from codeqa.adapters.python_complexity import extract_python_complexity
from codeqa.adapters.python_duplication import extract_python_token_blocks
from codeqa.adapters.python_snapshot import parse_python_snapshot
from codeqa.evaluation.complexity import ComplexityProfile, evaluate_complexity
from codeqa.evaluation.dependency_metrics import (
    DependencyMetricsProfile, evaluate_dependency_metrics,
)
from codeqa.evaluation.duplication import DuplicationProfile, evaluate_duplication
from codeqa.evaluation.mechanical import MechanicalProfile
from codeqa.evaluation.qa_result import (
    canonical_qa_json, compare_quality_delta, mechanical_to_qa_result,
)
from codeqa.evaluation.quality_delta_v02 import (
    QualityDeltaV02Error, build_source_change_manifest,
    compare_metric_snapshots, metric_snapshot_from_qa_result,
    validate_metric_snapshot,
)
from codeqa.evaluation.quality_delta_companions import (
    architecture_metric_rule, complexity_metric_rules,
    dependency_metric_rule, duplication_metric_rule,
)
from codeqa.evaluation.architecture_rules import evaluate_declared_architecture_rules
from codeqa.infrastructure.resources import ResourceRegistry
from codeqa.pipeline.python import analyze_python


ROOT = Path(__file__).resolve().parents[1]
REPO = "HyungseonSong-plasma/codeQA"
PIN_A = "a" * 40
PIN_B = "b" * 40


class QualityDeltaV02Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        reg = ResourceRegistry(ROOT)
        cls.ccg = reg.load_json("ccg_schema")
        cls.mechanical = reg.load_json("mechanical_profile")
        cls.old_result_schema = reg.load_json("qa_result_schema")
        cls.old_delta_schema = reg.load_json("qa_delta_schema")
        cls.snapshot_schema = reg.load_json("metric_snapshot_v02_schema")
        cls.delta_schema = reg.load_json("qa_delta_v02_schema")
        cls.change_schema = reg.load_json("source_change_v02_schema")
        cls.complexity = reg.load_json("complexity_profile")
        cls.duplication = reg.load_json("duplication_profile")
        cls.dependency = reg.load_json("dependency_metrics_profile")
        for schema in (cls.snapshot_schema, cls.delta_schema, cls.change_schema):
            Draft202012Validator.check_schema(schema)

    def base(self, sources, sha=PIN_A, repo=REPO, profile=None, companion=False):
        profile = profile or self.mechanical
        sid = f"git:{repo}@{sha}"
        result = analyze_python(
            sources, snapshot_id=sid, ccg_schema=self.ccg,
            mechanical_profile=profile,
        )
        old = mechanical_to_qa_result(
            result.graph, result.quality, MechanicalProfile.from_mapping(profile),
            schema=self.old_result_schema,
        )
        extras = []
        if companion:
            dep_profile = DependencyMetricsProfile.from_mapping(self.dependency)
            dep = evaluate_dependency_metrics(result.dependencies, dep_profile)
            extras.append(dependency_metric_rule(dep, dep_profile))
            parsed = parse_python_snapshot(sources)
            comp_profile = ComplexityProfile.from_mapping(self.complexity)
            comp = evaluate_complexity(result.graph,
                                       extract_python_complexity(parsed),
                                       comp_profile)
            extras.extend(complexity_metric_rules(comp, comp_profile))
            duplicate_profile = DuplicationProfile.from_mapping(self.duplication)
            tokens = extract_python_token_blocks(
                parsed, sources, snapshot_id=sid, profile=self.duplication,
            )
            duplication = evaluate_duplication(tokens, duplicate_profile)
            extras.append(duplication_metric_rule(duplication, duplicate_profile))
        doc = metric_snapshot_from_qa_result(
            old,
            {p: contents for p, contents in sources.items() if p in result.graph.coverage.analyzed_paths},
            repository=repo, commit_sha=sha,
            result_schema=self.old_result_schema,
            snapshot_schema=self.snapshot_schema,
            companions=tuple(extras),
        )
        return old, doc

    def compare(self, left, right, *, renames=(), manifest=None):
        changes = manifest or build_source_change_manifest(left, right, renames=renames)
        return compare_metric_snapshots(
            left, right, changes,
            snapshot_schema=self.snapshot_schema, change_schema=self.change_schema,
            delta_schema=self.delta_schema,
        )

    def test_v02_versions_are_independent_of_frozen_v01(self):
        self.assertEqual(self.snapshot_schema["$id"], "urn:codeqa:qa:metric-snapshot:v0.2")
        self.assertEqual(self.delta_schema["$id"], "urn:codeqa:qa:delta:v0.2")
        self.assertEqual(self.old_result_schema["$id"], "urn:codeqa:qa:result:v0.1")
        self.assertEqual(self.old_delta_schema["$id"], "urn:codeqa:qa:delta:v0.1")
        self.assertNotIn("rule_deltas", self.old_result_schema["properties"])

    def test_real_mechanical_rule_delta_and_stable_function_identity(self):
        profile = {**self.mechanical, "max_function_lines": 2}
        _, a = self.base({"app.py": "def f():\n    return 1\n"}, profile=profile)
        _, b = self.base({"app.py": "def f():\n    x = 1\n    return x\n"},
                         sha=PIN_B, profile=profile)
        result = self.compare(a, b)
        self.assertEqual(result["status"], "COMPARABLE")
        by_rule = {x["rule_id"]: x for x in result["rule_deltas"]}
        change = by_rule["function_span_review"]
        self.assertEqual(change["sum_delta"], 1)
        self.assertEqual(change["review_delta"], 1)
        self.assertEqual(change["observations"][0]["change"], "MATCHED")
        self.assertEqual(change["observations"][0]["value_delta"], 1)
        self.assertEqual(result["interpretation"],
                         "DESCRIPTIVE_METRIC_CHANGES_NOT_PROVEN_REGRESSIONS")

    def test_line_relocation_does_not_create_a_new_function(self):
        _, a = self.base({"a.py": "def f():\n    return 1\n"})
        _, b = self.base({"a.py": "\n\n\n\ndef f():\n    return 1\n"}, sha=PIN_B)
        result = self.compare(a, b)
        span = next(x for x in result["rule_deltas"]
                    if x["rule_id"] == "function_span_review")
        self.assertEqual(span["sum_delta"], 0)
        self.assertEqual(span["observations"][0]["change"], "MATCHED")
        self.assertEqual(span["observations"][0]["value_delta"], 0)

    def test_actual_renames_need_explicit_hash_grounding(self):
        _, a = self.base({"old.py": "def f():\n    return 1\n"})
        _, b = self.base({"renamed.py": "def f():\n    return 1\n"}, sha=PIN_B)
        incomplete = self.compare(a, b)
        self.assertEqual(incomplete["status"], "NOT_COMPARABLE")
        self.assertIn("selected_paths_changed_without_grounded_renames",
                      incomplete["reasons"])
        fixed = self.compare(a, b, renames=(("old.py", "renamed.py"),))
        self.assertEqual(fixed["status"], "COMPARABLE")
        self.assertEqual(fixed["rule_deltas"][0]["observations"][0]["path"], "old.py")
        false_manifest = build_source_change_manifest(a, b, renames=(("old.py", "renamed.py"),))
        false_manifest["renames"][0]["before_sha256"] = "0" * 64
        with self.assertRaises(QualityDeltaV02Error):
            self.compare(a, b, manifest=false_manifest)

    def test_same_source_bytes_cannot_support_conflicting_observations(self):
        src = {"x.py": "def f():\n    return 1\n"}
        _, a = self.base(src)
        _, b = self.base(src, sha=PIN_B)
        self.assertEqual(self.compare(a, b)["status"], "COMPARABLE")
        wrong = deepcopy(b)
        wrong["rules"][0]["observations"][0]["value"] += 10
        delta = self.compare(a, wrong)
        self.assertEqual(delta["status"], "PARTIAL")
        incompat = next(x for x in delta["rule_deltas"] if x["status"] == "NOT_COMPARABLE")
        self.assertIn("unchanged_source_bytes_conflicting_metrics", incompat["reasons"])

    def test_profile_version_units_and_denominator_fail_closed_per_rule(self):
        src = {"x.py": "def f():\n    return 1\n"}
        _, a = self.base(src)
        _, b = self.base({"x.py": "def f():\n    return 2\n"}, sha=PIN_B)
        for reason, mutation in (
            ("profile_changed", lambda d: d["rules"][0]["profile"].update({"fingerprint": "b"*64})),
            ("engine_changed", lambda d: d["rules"][0]["engine"].update({"version": "0.2"})),
            ("version_changed", lambda d: d["rules"][0].update({"version": "0.2"})),
            ("metric_changed", lambda d: d["rules"][0]["metric"].update({"unit": "second"})),
            ("denominator_changed", lambda d: d["rules"][0]["denominator"].update({"value": 2})),
        ):
            with self.subTest(reason=reason):
                changed = deepcopy(b)
                mutation(changed)
                result = self.compare(a, changed)
                self.assertEqual(result["status"], "PARTIAL")
                self.assertIn(reason, next(x for x in result["rule_deltas"]
                              if x["rule_id"] == a["rules"][0]["id"])["reasons"])

    def test_partial_parse_is_never_imputed_to_zero(self):
        _, a = self.base({"good.py": "def f():\n    return 1\n",
                          "broken.py": "def ("})
        _, b = self.base({"good.py": "def f():\n    return 2\n",
                          "broken.py": "def ("}, sha=PIN_B)
        result = self.compare(a, b)
        self.assertEqual(result["status"], "NOT_COMPARABLE")
        self.assertIn("incomplete_or_failed_source_parsing", result["reasons"])

    def test_companion_metrics_are_real_and_scoped_not_invented(self):
        source = {"x.py": "def f(x):\n    n = x + 2\n    return n * 4\n"}
        _, a = self.base(source, companion=True)
        _, b = self.base({"x.py": "def f(x):\n    n = x + 3\n    return n * 4\n"},
                         sha=PIN_B, companion=True)
        names = {r["id"] for r in a["rules"]}
        self.assertEqual(names, {
            "function_span_review", "outgoing_call_sites_review",
            "static_fan_out_review", "cyclomatic_proxy_review",
            "branch_nesting_review", "normalized_duplicate_fraction",
        })
        self.assertNotIn("P6", {x["id"] for x in a["unsupported_principles"]})
        result = self.compare(a, b)
        self.assertEqual(result["status"], "COMPARABLE")
        self.assertTrue(all(rule["status"] == "COMPARABLE" for rule in result["rule_deltas"]))
        self.assertEqual(next(x for x in result["rule_deltas"]
                              if x["rule_id"] == "normalized_duplicate_fraction")["sum_delta"], 0)

    def test_real_architecture_policy_companion_preserves_source_witness(self):
        policy = {
            "schema_version": "0.1", "policy_id": "fixture.roles",
            "revision": "2026-10-23", "scope": "src/pkg",
            "effective_from": "2026-01-01",
            "temporality": "CONTEMPORANEOUS",
            "scope_inventory_complete": True,
            "roles": {
                "core": {
                    "responsibility": "facts", "allowed_imports": ["core"],
                    "forbidden_imports": ["api"],
                },
                "api": {
                    "responsibility": "api",
                    "allowed_imports": ["api", "core"], "forbidden_imports": [],
                },
            },
            "exceptions": [],
        }
        sources = {
            "src/pkg/core/mod.py": "from pkg.api import entry\n",
            "src/pkg/api/__init__.py": "entry = 1\n",
        }
        sha = PIN_A
        snapshot_id = f"git:{REPO}@{sha}"
        analysis = analyze_python(
            sources, snapshot_id=snapshot_id,
            ccg_schema=self.ccg, mechanical_profile=self.mechanical,
        )
        rule_schema = (ROOT / "contracts/semantic/declared-rule-policy-v0.1.schema.json")
        import json
        report = evaluate_declared_architecture_rules(
            analysis.graph, analysis.dependencies, policy,
            schema=json.loads(rule_schema.read_text(encoding="utf-8")),
            source_as_of="2026-10-23",
        )
        companion = architecture_metric_rule(
            report, policy, analyzed_paths=analysis.graph.coverage.analyzed_paths,
        )
        self.assertEqual(companion["evidence_status"], "MEASURED")
        self.assertEqual(companion["observations"][0]["value"], 1)
        self.assertEqual(companion["observations"][0]["path"], "src/pkg/core/mod.py")
        qa = mechanical_to_qa_result(
            analysis.graph, analysis.quality,
            MechanicalProfile.from_mapping(self.mechanical),
            schema=self.old_result_schema,
        )
        snapshot = metric_snapshot_from_qa_result(
            qa, sources, repository=REPO, commit_sha=sha,
            result_schema=self.old_result_schema,
            snapshot_schema=self.snapshot_schema, companions=(companion,),
        )
        self.assertIn("declared_policy_violation_witnesses",
                      {rule["id"] for rule in snapshot["rules"]})
        self.assertNotIn("P4",
                         {x["id"] for x in snapshot["unsupported_principles"]})

    def test_one_unsupported_or_incomplete_companion_remains_not_comparable(self):
        source = {"x.py": "def f():\n    return 1\n"}
        _, a = self.base(source)
        _, b = self.base({"x.py": "def f():\n    return 2\n"}, sha=PIN_B, companion=True)
        result = self.compare(a, b)
        self.assertEqual(result["status"], "PARTIAL")
        self.assertIn("rule_missing_or_unsupported_in_one_snapshot",
                      next(x for x in result["rule_deltas"]
                           if x["rule_id"] == "cyclomatic_proxy_review")["reasons"])

    def test_snapshot_mismatch_and_duplicate_subjects_raise(self):
        source = {"x.py": "def f():\n    return 1\n"}
        _, a = self.base(source)
        _, b = self.base(source, sha=PIN_B)
        for mutation in ("incorrect_source_id", "missing_path", "duplicate_subject",
                         "unsupported_principle", "nonfinite"):
            with self.subTest(mutation=mutation), self.assertRaises(QualityDeltaV02Error):
                changed = deepcopy(a)
                if mutation == "incorrect_source_id":
                    changed["snapshot_id"] = "unverified"
                elif mutation == "missing_path":
                    changed["source"]["files"].clear()
                elif mutation == "duplicate_subject":
                    changed["rules"][0]["observations"].append(
                        deepcopy(changed["rules"][0]["observations"][0]))
                    changed["rules"][0]["denominator"]["value"] += 1
                elif mutation == "unsupported_principle":
                    changed["unsupported_principles"].pop()
                else:
                    changed["rules"][0]["observations"][0]["value"] = float("nan")
                validate_metric_snapshot(changed, self.snapshot_schema)
        with self.assertRaises(QualityDeltaV02Error):
            self.compare(a, self.base(source, sha=PIN_B, repo="another/repo")[1])

    def test_old_v01_path_and_pinned_cross_repo_refs_are_preserved(self):
        source = {"x.py": "def f():\n    return 1\n"}
        old_a, _ = self.base(source)
        old_b, _ = self.base(source, sha=PIN_B)
        old_delta = compare_quality_delta(
            old_a, old_b,
            result_schema=self.old_result_schema, delta_schema=self.old_delta_schema,
        )
        self.assertEqual(old_delta["schema_version"], "0.1")
        self.assertEqual(old_delta["interpretation"], "descriptive_review_counts_only")
        self.assertEqual(canonical_qa_json(old_a),
                         canonical_qa_json(deepcopy(old_a)))
        samuel = ROOT / "fixtures/samuel/controller/bootstrap.py.txt"
        moose = ROOT / "fixtures/mixed/python/physics_dependency_guard.py.txt"
        self.assertTrue(samuel.is_file() and moose.is_file())
        sha_samuel = "9b335e3fbb9c5e8e323e382daeec56fa25336822"
        sha_moose = "1977ad5559e5aa7a1c8d04c83735c15e007130d5"
        # Different pinned repositories can each be analyzed but NOT merged.
        _, a = self.base({"controller/bootstrap.py": samuel.read_text()},
                         sha=sha_samuel, repo="HyungseonSong-plasma/chatgpt-operation")
        _, b = self.base({"guard.py": moose.read_text()},
                         sha=sha_moose, repo="HyungseonSong-plasma/moose-test-repo")
        with self.assertRaises(QualityDeltaV02Error):
            self.compare(a, b)

    def test_repeatability_and_no_mutation(self):
        _, a = self.base({"a.py": "def f():\n    return 1\n"})
        _, b = self.base({"a.py": "def f():\n    return 2\n"}, sha=PIN_B)
        before = deepcopy(a)
        first = self.compare(a, b)
        again = self.compare(deepcopy(a), deepcopy(b))
        self.assertEqual(canonical_qa_json(first), canonical_qa_json(again))
        self.assertEqual(a, before)


if __name__ == "__main__":
    unittest.main()
