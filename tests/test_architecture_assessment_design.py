"""Issue A: design-contract tests for evidence-first architecture question discovery.

DESIGN_ONLY: these tests do not assert that production discovery runs yet.
They ensure later B1-B8 implementations cannot silently substitute fixed
Naming/Adapter prompts for source-triggered opportunities.
"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import re
import unittest
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "fixtures/architecture/design-scenarios-v0.1.json"
DESIGN_PATH = ROOT / "docs/architecture-assessment-design-v0.1.md"
ROLE_POLICY_PATH = ROOT / "profiles/semantic-directory-roles-v0.1.json"

EXPECTED_REGRESSION_IDS = {"L0", "L1", "L2", "L3"}
EXPECTED_EVIDENCE = {
    "OBSERVED", "DECLARED_POLICY", "PROXY_INFERENCE", "HUMAN_REVIEW",
}
EXPECTED_DECISIONS = {
    "PREFER", "KEEP", "REVIEW_REQUIRED", "INSUFFICIENT_EVIDENCE",
}
EXPECTED_ROLES = {
    "core", "adapters", "evaluation", "pipeline", "governance",
    "infrastructure",
}
SIGNAL_FIELDS = {
    "signal_id", "family", "scope", "source_witnesses",
    "measurements_and_denominators", "coverage", "unknowns",
    "counterhypotheses", "severity_or_opportunity", "derivation_rule",
}
OPPORTUNITY_FIELDS = {
    "opportunity_id", "originating_signals", "affected_owners",
    "source_witnesses", "diagnostic_reason", "candidate_decision_question",
    "plausible_alternatives", "counterarguments", "missing_evidence",
    "confidence_limitations",
}
REQUIRED_RECORD_FIELDS = {
    "scenario_id", "snapshot_sha", "analyzer_version", "profile_sha256",
    "source_coverage", "source_witnesses", "metrics_with_denominators",
    "unknowns", "migration_impact", "tradeoffs", "decision",
    "decision_reasons", "review_question", "originating_signals",
    "candidate_decision_question", "derivation_rule", "counterhypotheses",
}


def source_path_ok(value: object) -> bool:
    """Check planned POSIX repo paths, including ones not shipped in Issue A."""
    return (
        isinstance(value, str) and bool(value)
        and not value.startswith("/") and "\\" not in value
        and all(32 <= ord(char) <= 126 for char in value)
        and all(p not in ("", ".", "..") for p in value.split("/"))
    )


def validate_design(data: dict) -> None:
    assert data["schema_version"] == "0.1"
    assert data["design_id"] == "codeqa.architecture-assessment-design.v0.1"
    assert data["phase"] == "DESIGN_ONLY"
    assert data["approval_status"] == "PROPOSED"
    assert data["design_intent"] == (
        "EVIDENCE_FIRST_QUESTION_DISCOVERY_NOT_PRESELECTED_ARCHITECTURE_QUESTIONS"
    )
    # Never accept an input questionnaire as the driver's architecture signals.
    assert "scenarios" not in data
    discovery = data["discovery"]
    assert discovery["requires_preseeded_question"] is False
    assert discovery["applies_to_arbitrary_repository"] is True
    assert discovery["emission_policy"]["zero_or_more_questions"] is True
    assert discovery["emission_policy"]["no_forced_naming_or_adapter_question"] is True
    assert discovery["emission_policy"]["no_signal"] == "EMPTY_OPPORTUNITIES_NOT_FALSE_PASS"
    assert discovery["emission_policy"]["candidate_question"] == (
        "DERIVE_FROM_MEASURED_SIGNALS_NOT_FROM_REPOSITORY_NAME_OR_TEST_CASE"
    )
    assert "extract_source_facts" == discovery["stages"][0]
    assert "detect_structural_signals" in discovery["stages"]
    assert "assemble_evidence_packs" in discovery["stages"]
    assert "surface_question_opportunities_to_chatgpt" in discovery["stages"]
    assert "evaluate_counterfactuals_with_compatibility_gates" in discovery["stages"]
    assert "unknown_and_unresolved_evidence" in discovery["minimum_source_evidence"]
    assert set(discovery["required_signal_fields"]) == SIGNAL_FIELDS
    assert set(discovery["required_opportunity_fields"]) == OPPORTUNITY_FIELDS
    assert len(discovery["signal_families"]) >= 4
    assert len({s["id"] for s in discovery["signal_families"]}) == len(discovery["signal_families"])
    assert len(discovery["anti_tautology_tests"]) >= 6
    assert "unrelated_repository_fixture" in discovery["anti_tautology_tests"]
    for signal in discovery["signal_families"]:
        assert re.fullmatch(r"[A-Z_]+", signal["id"])
        assert len(signal["evidence"]) >= 2
        assert signal["hypothesis"] and signal["counterexample"]
        # No source/repo/domain name hardcoded into generic detectors.
        assert "Naming" not in signal["id"]
        assert "Adapter" not in signal["id"]

    authority = data["authority"]
    for path in (
        authority["frozen_repository_root"],
        authority["package_structure"],
        authority["role_policy"],
        *authority["evidence_sources"],
    ):
        assert source_path_ok(path)
        assert (ROOT / path).is_file(), path

    roles = data["ownership"]
    assert set(roles) == EXPECTED_ROLES
    policy = json.loads(ROLE_POLICY_PATH.read_text(encoding="utf-8"))
    assert set(policy["roles"]) == EXPECTED_ROLES
    for name, role in roles.items():
        assert role["path"] == "src/codeqa/" + name
        assert role["responsibility"].strip()
        assert len(role["may_import"]) == len(set(role["may_import"]))
        assert set(role["may_import"]) <= EXPECTED_ROLES - {name}
        forbidden = set(policy["roles"][name]["forbidden_imports"])
        assert not forbidden.intersection(role["may_import"])

    components = data["proposed_components"]
    paths = [component["path"] for component in components]
    assert len(paths) == len(set(paths))
    assert {"core", "evaluation", "pipeline"} <= {c["owner"] for c in components}
    for component in components:
        assert component["owner"] in roles
        assert source_path_ok(component["path"])
        assert component["path"].startswith(roles[component["owner"]]["path"] + "/") or (
            component["owner"] == "pipeline"
            and component["path"] == ".github/scripts/architecture_audit.py"
        )
        assert component["purpose"].strip()

    examples = data["regression_examples"]
    assert len(examples) == len(EXPECTED_REGRESSION_IDS)
    assert {example["example_id"] for example in examples} == EXPECTED_REGRESSION_IDS
    assert all(
        example["role"] == "REGRESSION_QUESTION_FAMILY_ONLY_NOT_ANALYZER_INPUT"
        and example["evidence_status"] == "NOT_MEASURED_BY_DESIGN"
        for example in examples
    )
    expected_paths = {
        "L1": {"src/codeqa/naming"},
        "L2": {"src/adapters"},
        "L3": {
            "src/codeqa/adapters/pythonqa",
            "src/codeqa/adapters/rustqa",
            "src/codeqa/adapters/cppqa",
            "src/adapters/pythonqa",
            "src/adapters/rustqa",
            "src/adapters/cppqa",
        },
    }
    for example in examples:
        roots = example["possible_layout_candidates"]
        assert roots and len(roots) == len(set(roots))
        assert example["known_evidence_needs"]
        for path in roots:
            assert source_path_ok(path) and path.startswith("src/")
        if example["example_id"] in expected_paths:
            assert set(roots) == expected_paths[example["example_id"]]

    comparison = data["comparison"]
    assert set(comparison["evidence_classes"]) == EXPECTED_EVIDENCE
    assert set(comparison["decisions"]) == EXPECTED_DECISIONS
    assert set(comparison["required_record_fields"]) == REQUIRED_RECORD_FIELDS
    assert set(comparison["required_signal_fields"]) == SIGNAL_FIELDS
    assert set(comparison["required_opportunity_fields"]) == OPPORTUNITY_FIELDS
    assert {
        "unknown_external_consumers", "dynamic_imports",
        "unresolved_language_parsers", "policy_conflict",
        "noncomparable_coverage",
    } <= set(comparison["fail_closed_on"])
    assert {
        "production_source_move", "rename", "adapter_relocation",
        "public_api_change", "ccg_v01_change",
        "qa_result_v01_change", "auto_migration",
        "hardcoded_preselected_questions",
    } <= set(data["prohibitions"])


class ArchitectureAssessmentDesignTests(unittest.TestCase):
    def load(self) -> dict:
        return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    def test_design_matches_role_policy_and_no_preselected_questions(self) -> None:
        validate_design(self.load())

    def test_design_document_explains_discovery_and_four_nonbinding_examples(self) -> None:
        text = DESIGN_PATH.read_text(encoding="utf-8")
        for item in ("L0", "L1", "L2", "L3", "INSUFFICIENT_EVIDENCE",
                     "PROXY_INFERENCE", "Human decision at Issue A",
                     "separately authorized migration", "NOT_EVALUATED",
                     "Question", "Evidence", "No-signal is valid",
                     "unrelated repository", "not compulsory analysis inputs"):
            with self.subTest(item=item):
                self.assertIn(item.lower(), text.lower())
        self.assertIn("not shipped by A", text)
        self.assertIn("no actual source move", text.lower())

    def test_local_document_links_resolve(self) -> None:
        text = DESIGN_PATH.read_text(encoding="utf-8")
        links = re.findall(r"(?<!!)\[[^\]\n]+\]\(([^)\s]+)\)", text)
        self.assertGreater(len(links), 5)
        for link in links:
            uri = urlsplit(link)
            if uri.scheme in ("https", "http", "mailto") or not uri.path:
                continue
            with self.subTest(link=link):
                target = (DESIGN_PATH.parent / unquote(uri.path)).resolve()
                self.assertTrue(target.is_relative_to(ROOT))
                self.assertTrue(target.is_file(), link)

    def test_missing_duplicate_or_runtime_seeded_examples_fail_closed(self) -> None:
        missing = deepcopy(self.load())
        missing["regression_examples"].pop()
        with self.assertRaises(AssertionError):
            validate_design(missing)
        duplicate = deepcopy(self.load())
        duplicate["regression_examples"].append(duplicate["regression_examples"][0])
        with self.assertRaises(AssertionError):
            validate_design(duplicate)
        seeded = deepcopy(self.load())
        seeded["scenarios"] = seeded["regression_examples"]
        with self.assertRaises(AssertionError):
            validate_design(seeded)

    def test_unsafe_paths_and_invalid_ownership_fail_closed(self) -> None:
        invalid = deepcopy(self.load())
        invalid["regression_examples"][2]["possible_layout_candidates"] = ["../../outside"]
        with self.assertRaises(AssertionError):
            validate_design(invalid)
        invalid = deepcopy(self.load())
        invalid["proposed_components"][0]["path"] = "src/codeqa/adapters/architecture.py"
        with self.assertRaises(AssertionError):
            validate_design(invalid)
        invalid = deepcopy(self.load())
        invalid["regression_examples"][2]["possible_layout_candidates"] = ["src/adapters", "new-root/adapters"]
        with self.assertRaises(AssertionError):
            validate_design(invalid)

    def test_premature_certification_or_forced_question_fails_closed(self) -> None:
        for section, field, value in [
            ("discovery", "requires_preseeded_question", True),
            ("discovery", "applies_to_arbitrary_repository", False),
        ]:
            with self.subTest(section=section, field=field):
                bad = deepcopy(self.load())
                bad[section][field] = value
                with self.assertRaises(AssertionError):
                    validate_design(bad)
        bad = deepcopy(self.load())
        bad["discovery"]["emission_policy"]["zero_or_more_questions"] = False
        with self.assertRaises(AssertionError):
            validate_design(bad)
        bad = deepcopy(self.load())
        bad["phase"] = "IMPLEMENTED"
        with self.assertRaises(AssertionError):
            validate_design(bad)
        bad = deepcopy(self.load())
        bad["comparison"]["decisions"].append("OPTIMAL_PASS")
        with self.assertRaises(AssertionError):
            validate_design(bad)
        bad = deepcopy(self.load())
        bad["comparison"]["required_opportunity_fields"].remove("missing_evidence")
        with self.assertRaises(AssertionError):
            validate_design(bad)
        bad = deepcopy(self.load())
        bad["prohibitions"].remove("hardcoded_preselected_questions")
        with self.assertRaises(AssertionError):
            validate_design(bad)


if __name__ == "__main__":
    unittest.main()
