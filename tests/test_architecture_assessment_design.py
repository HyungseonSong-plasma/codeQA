"""Design-only contract checks for Architecture QA Issue A (#165).

These tests validate the proposed design manifest and references. They do NOT
claim that B1-B8 evaluators already exist or that a package migration is safe.
"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path, PurePosixPath
import re
import unittest
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "fixtures/architecture/design-scenarios-v0.1.json"
DESIGN_PATH = ROOT / "docs/architecture-assessment-design-v0.1.md"
ROLE_POLICY_PATH = ROOT / "profiles/semantic-directory-roles-v0.1.json"

EXPECTED_SCENARIOS = {"L0", "L1", "L2", "L3"}
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
REQUIRED_RECORD_FIELDS = {
    "scenario_id", "snapshot_sha", "analyzer_version", "profile_sha256",
    "source_coverage", "source_witnesses", "metrics_with_denominators",
    "unknowns", "migration_impact", "tradeoffs", "decision",
    "decision_reasons", "review_question",
}


def source_path_ok(value: object) -> bool:
    """Validate *proposed* POSIX repo paths without requiring them to exist."""
    if not isinstance(value, str) or "\\" in value or "\x00" in value:
        return False
    if value.startswith("/") or re.search(r"[^\x20-\x7e]", value):
        return False
    parts = PurePosixPath(value).parts
    return bool(parts) and all(part not in ("", ".", "..") for part in value.split("/"))


def validate_design(data: dict) -> None:
    """Small fail-closed structural guard, not a future production schema."""
    assert data["schema_version"] == "0.1"
    assert data["design_id"] == "codeqa.architecture-assessment-design.v0.1"
    assert data["phase"] == "DESIGN_ONLY"
    assert data["approval_status"] == "PROPOSED"

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
    role_policy = json.loads(ROLE_POLICY_PATH.read_text(encoding="utf-8"))
    assert set(role_policy["roles"]) == EXPECTED_ROLES
    for name, definition in roles.items():
        assert definition["path"] == "src/codeqa/" + name
        assert bool(definition["responsibility"].strip())
        assert len(definition["may_import"]) == len(set(definition["may_import"]))
        assert set(definition["may_import"]) <= EXPECTED_ROLES - {name}
        forbidden = set(role_policy["roles"][name]["forbidden_imports"])
        assert not forbidden.intersection(definition["may_import"])

    proposed = data["proposed_components"]
    paths = [entry["path"] for entry in proposed]
    assert len(paths) == len(set(paths))
    assert {"core", "evaluation", "pipeline"} <= {entry["owner"] for entry in proposed}
    for entry in proposed:
        assert entry["owner"] in roles
        assert source_path_ok(entry["path"])
        assert entry["path"].startswith(roles[entry["owner"]]["path"] + "/") or (
            entry["owner"] == "pipeline"
            and entry["path"] == ".github/scripts/architecture_audit.py"
        )
        assert bool(entry["purpose"].strip())

    scenarios = data["scenarios"]
    ids = [item["id"] for item in scenarios]
    assert len(ids) == len(set(ids))
    assert set(ids) == EXPECTED_SCENARIOS
    baseline = next(item for item in scenarios if item["id"] == "L0")
    assert baseline["kind"] == "BASELINE"
    assert all(item["kind"] == "COUNTERFACTUAL" for item in scenarios if item["id"] != "L0")
    required_paths = {
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
    for scenario in scenarios:
        roots = scenario["candidate_package_roots"]
        assert roots and len(roots) == len(set(roots))
        assert scenario["question"].endswith("?")
        assert scenario["requires"]
        for path in roots:
            assert source_path_ok(path)
            assert path.startswith("src/")  # no new top-level repo directories
        if scenario["id"] in required_paths:
            assert set(roots) == required_paths[scenario["id"]]

    comparison = data["comparison"]
    assert set(comparison["evidence_classes"]) == EXPECTED_EVIDENCE
    assert set(comparison["decisions"]) == EXPECTED_DECISIONS
    assert set(comparison["required_record_fields"]) == REQUIRED_RECORD_FIELDS
    assert {
        "unknown_external_consumers", "dynamic_imports",
        "unresolved_language_parsers", "policy_conflict",
        "noncomparable_coverage",
    } <= set(comparison["fail_closed_on"])
    assert {"production_source_move", "rename", "adapter_relocation",
            "public_api_change", "ccg_v01_change",
            "qa_result_v01_change", "auto_migration"} <= set(data["prohibitions"])


class ArchitectureAssessmentDesignTests(unittest.TestCase):
    def load(self) -> dict:
        return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    def test_manifest_matches_existing_layout_policy_and_roles(self) -> None:
        validate_design(self.load())

    def test_design_document_answers_four_questions_without_claiming_implementation(self) -> None:
        text = DESIGN_PATH.read_text(encoding="utf-8")
        for key in ("L0", "L1", "L2", "L3", "INSUFFICIENT_EVIDENCE",
                    "PROXY_INFERENCE", "Human decision at Issue A",
                    "separately authorized migration", "NOT_EVALUATED"):
            with self.subTest(key=key):
                self.assertIn(key, text)
        self.assertIn("design-only", text.lower())
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

    def test_missing_or_duplicate_scenarios_fail_closed(self) -> None:
        missing = deepcopy(self.load())
        missing["scenarios"] = missing["scenarios"][:-1]
        with self.assertRaises(AssertionError):
            validate_design(missing)
        duplicate = deepcopy(self.load())
        duplicate["scenarios"].append(deepcopy(duplicate["scenarios"][0]))
        with self.assertRaises(AssertionError):
            validate_design(duplicate)

    def test_unsafe_or_wrong_package_paths_fail_closed(self) -> None:
        invalid = deepcopy(self.load())
        invalid["scenarios"][2]["candidate_package_roots"] = ["../../outside"]
        with self.assertRaises(AssertionError):
            validate_design(invalid)
        invalid = deepcopy(self.load())
        invalid["proposed_components"][0]["path"] = "src/codeqa/adapters/architecture.py"
        with self.assertRaises(AssertionError):
            validate_design(invalid)
        invalid = deepcopy(self.load())
        invalid["scenarios"][2]["candidate_package_roots"] = ["src/adapters", "new-root/adapters"]
        with self.assertRaises(AssertionError):
            validate_design(invalid)

    def test_no_premature_implementation_or_recommendation_certification(self) -> None:
        implemented = deepcopy(self.load())
        implemented["phase"] = "IMPLEMENTED"
        with self.assertRaises(AssertionError):
            validate_design(implemented)
        weak = deepcopy(self.load())
        weak["comparison"]["decisions"].append("OPTIMAL_PASS")
        with self.assertRaises(AssertionError):
            validate_design(weak)
        weak = deepcopy(self.load())
        weak["comparison"]["required_record_fields"].remove("unknowns")
        with self.assertRaises(AssertionError):
            validate_design(weak)
        unauthorized = deepcopy(self.load())
        unauthorized["prohibitions"].remove("auto_migration")
        with self.assertRaises(AssertionError):
            validate_design(unauthorized)


if __name__ == "__main__":
    unittest.main()
