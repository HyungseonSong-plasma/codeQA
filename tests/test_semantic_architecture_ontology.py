"""Ground truth for Semantic Architecture Ontology v0.1."""
from __future__ import annotations

import json
from pathlib import Path
import unittest

from jsonschema import Draft202012Validator
from codeqa.infrastructure.resources import ResourceRegistry
from codeqa.pipeline.python import analyze_python

ROOT = Path(__file__).resolve().parents[1]


def roles():
    return {
        "policy_id": "test.semantic.v0.1", "schema_version": 1,
        "scope": "src/pkg",
        "roles": {
            "core": {"responsibility": "Immutable models",
                     "forbidden_imports": ["evaluation"]},
            "evaluation": {"responsibility": "Pure evaluation",
                           "forbidden_imports": []},
        },
        "exceptions": [],
    }


class SemanticArchitectureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        registry = ResourceRegistry(ROOT)
        cls.ccg = registry.load_json("ccg_schema")
        cls.profile = registry.load_json("mechanical_profile")
        cls.schema = json.loads(
            (ROOT / "contracts/semantic/architecture-v0.1.schema.json").read_text()
        )
        cls.vocab = json.loads(
            (ROOT / "contracts/semantic/architecture-v0.1.vocabulary.json").read_text()
        )

    def analyze(self, sources, policy=None):
        return analyze_python(
            sources, snapshot_id="fixed-sha", ccg_schema=self.ccg,
            mechanical_profile=self.profile,
            semantic_policy=roles() if policy is None else policy,
        )

    def test_schema_and_vocabulary_are_valid_and_exact(self):
        from codeqa.core.semantic_architecture import ENTITY_KINDS, RELATION_KINDS, ASSURANCES
        Draft202012Validator.check_schema(self.schema)
        self.assertEqual(set(self.vocab["entity_kinds"]), ENTITY_KINDS)
        self.assertEqual(set(self.vocab["relation_kinds"]), RELATION_KINDS)
        self.assertEqual(set(self.vocab["assurances"]), ASSURANCES)

    def test_roles_and_import_facts_stay_distinct_and_typed(self):
        r = self.analyze({
            "src/pkg/core/model.py": "x = 1\n",
            "src/pkg/evaluation/rules.py": "import pkg.core.model as core\n",
        }).semantic_architecture
        self.assertEqual(r.status, "NOT_EVALUATED")
        by_kind = {}
        for rel in r.relations:
            by_kind.setdefault(rel.kind, []).append(rel)
        self.assertTrue(any(
            x.source == "role:core" and x.target == "responsibility:core"
            and x.assurance == "POLICY_DECLARATION"
            for x in by_kind["owns_responsibility"]
        ))
        self.assertTrue(any(
            x.source == "role:core" and x.target == "role:evaluation"
            for x in by_kind["prohibited_dependency"]
        ))
        self.assertTrue(any(
            x.source == "file:src/pkg/evaluation/rules.py"
            and x.target == "file:src/pkg/core/model.py"
            and x.assurance == "STATIC_MODULE_PATH"
            for x in by_kind["imports"]
        ))
        kinds = {e.id: e.kind for e in r.entities}
        for edge in r.relations:
            self.assertIn(edge.source, kinds)
            self.assertIn(edge.target, kinds)
            self.assertEqual(
                [kinds[edge.source], kinds[edge.target]],
                self.vocab["relation_kinds"][edge.kind],
            )
        self.assertIn("behavior_vs_responsibility", r.unassessed_dimensions)

    def test_forbidden_edge_has_real_source_witness(self):
        r = self.analyze({
            "src/pkg/evaluation/__init__.py": "",
            "src/pkg/core/mod.py": "from pkg.evaluation import evaluator\n",
        }).semantic_architecture
        failures = [a for a in r.assessments if a.status == "VIOLATION"]
        self.assertEqual(len(failures), 1)
        self.assertEqual(failures[0].code, "FORBIDDEN_ROLE_DEPENDENCY")
        self.assertEqual(failures[0].source, "src/pkg/core/mod.py")
        self.assertIsNotNone(failures[0].evidence_id)
        self.assertIn("evidence:" + failures[0].evidence_id,
                      {e.id for e in r.entities})
        self.assertEqual(r.status, "VIOLATION")

    def test_two_import_statements_one_line_have_no_guessed_witness(self):
        r = self.analyze({
            "src/pkg/evaluation/__init__.py": "",
            "src/pkg/evaluation/util.py": "",
            "src/pkg/core/mod.py": "import pkg.evaluation; import pkg.evaluation.util\n",
        }).semantic_architecture
        failures = [a for a in r.assessments if a.status == "VIOLATION"]
        self.assertEqual(len(failures), 2)
        self.assertTrue(all(a.evidence_id is None for a in failures))
        self.assertFalse(any(rel.kind == "supported_by" for rel in r.relations))

    def test_transition_is_review_new_edge_violation(self):
        p = roles()
        p["exceptions"] = [{
            "source": "src/pkg/core/legacy.py",
            "target": "src/pkg/evaluation/__init__.py",
            "status": "TRANSITIONAL_REVIEW", "rationale": "migrate legacy",
        }]
        r = self.analyze({
            "src/pkg/evaluation/__init__.py": "",
            "src/pkg/core/legacy.py": "import pkg.evaluation\n",
            "src/pkg/core/new.py": "import pkg.evaluation\n",
        }, p).semantic_architecture
        self.assertEqual(
            {x.code for x in r.assessments},
            {"DECLARED_TRANSITIONAL_EDGE", "FORBIDDEN_ROLE_DEPENDENCY"},
        )
        self.assertEqual(r.status, "VIOLATION")

    def test_missing_and_unclassified_roles_are_explicit(self):
        r = self.analyze({
            "src/pkg/core/mod.py": "pass\n",
            "src/pkg/unknown/mod.py": "pass\n",
        }).semantic_architecture
        self.assertEqual(
            {x.code for x in r.assessments},
            {"MISSING_DECLARED_ROLE", "UNCLASSIFIED_ROLE"},
        )

    def test_partial_parse_does_not_claim_missing_role_violation(self):
        r = self.analyze({
            "src/pkg/core/mod.py": "pass\n",
            "src/pkg/evaluation/broken.py": "def broken(:\n",
        }).semantic_architecture
        self.assertIn("PARTIAL_SOURCE_COVERAGE",
                      {x.code for x in r.assessments})
        self.assertNotIn("MISSING_DECLARED_ROLE",
                         {x.code for x in r.assessments})
        self.assertEqual(r.status, "NOT_EVALUATED")

    def test_unknown_dependency_is_not_inferred_as_runtime_edge(self):
        r = self.analyze({
            "src/pkg/core/mod.py": "import absent_external\n",
            "src/pkg/evaluation/rule.py": "pass\n",
        }).semantic_architecture
        self.assertIn("UNMAPPED_IMPORT_SEMANTICS",
                      {a.code for a in r.assessments})
        self.assertFalse(any(x.kind == "imports" for x in r.relations))
        self.assertEqual(r.status, "NOT_EVALUATED")

    def test_inconsistent_snapshots_fail_closed(self):
        from dataclasses import replace
        from codeqa.evaluation.semantic_architecture import evaluate_semantic_architecture
        a = self.analyze({
            "src/pkg/core/mod.py": "pass\n",
            "src/pkg/evaluation/rule.py": "pass\n",
        })
        with self.assertRaises(ValueError):
            evaluate_semantic_architecture(
                a.graph, replace(a.dependencies, snapshot_id="other"),
                a.evidence, roles(),
            )

    def test_optional_feature_leaves_legacy_reports_unchanged(self):
        sources = {
            "src/pkg/core/mod.py": "pass\n",
            "src/pkg/evaluation/rule.py": "pass\n",
        }
        normal = analyze_python(sources, snapshot_id="fixed-sha",
            ccg_schema=self.ccg, mechanical_profile=self.profile)
        enriched = self.analyze(sources)
        self.assertIsNone(normal.semantic_architecture)
        self.assertEqual(normal.summary_document()["semantic_architecture"]["status"],
                         "NOT_REQUESTED")
        for attr in ("graph", "quality", "dependencies", "evidence", "symbol_calls"):
            self.assertEqual(getattr(normal, attr), getattr(enriched, attr))

    def test_serialization_and_determinism(self):
        sources = {
            "src/pkg/core/a.py": "def f(): return 1\n",
            "src/pkg/evaluation/b.py": "from pkg.core.a import f\n"
                                        "def g(): return f()\n",
        }
        first = self.analyze(sources).semantic_architecture
        other = self.analyze(dict(reversed(list(sources.items())))).semantic_architecture
        self.assertEqual(first, other)
        Draft202012Validator(self.schema).validate(first.to_document())
        json.dumps(first.to_document(), sort_keys=True)

    def test_moose_subset_never_broadens_narrow_adapter_constraints(self):
        moose = json.loads(
            (ROOT / "profiles/moose-test-directory-roles-subset-v0.1.json").read_text()
        )
        self.assertEqual(moose["scope"], "physics_harness")
        self.assertEqual(len(moose["roles"]), 15)
        self.assertEqual(moose["roles"]["application"]["forbidden_imports"], [])
        self.assertEqual(moose["roles"]["ontology"]["forbidden_imports"], [])
        self.assertIn("validation", moose["roles"]["analysis"]["forbidden_imports"])
        self.assertEqual(moose["assessment_temporality"], "RETROSPECTIVE_PINNED_SOURCE")

    def test_function_names_do_not_imply_behavior(self):
        r = self.analyze({
            "src/pkg/core/execute_runtime.py": "def execute(): return 'text'\n",
            "src/pkg/evaluation/a.py": "pass\n",
        }).semantic_architecture
        self.assertFalse(any(x.kind == "exhibits_behavior" for x in r.relations))
        self.assertIn("scientific_domain_contract", r.unassessed_dimensions)
        self.assertEqual(r.status, "NOT_EVALUATED")


if __name__ == "__main__":
    unittest.main()
