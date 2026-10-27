"""Architecture B1 inventory tests: arbitrary paths, unknowns and real source."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import unittest

from jsonschema import Draft202012Validator

from codeqa.evaluation.architecture.inventory import (
    ArchitectureInventoryError,
    analyze_architecture_inventory,
)
from codeqa.infrastructure.git import GitReader


ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = "a" * 40
ROLE_POLICY = {
    "policy_id": "fixture.roles.v0.1",
    "scope": "src/widget",
    "roles": {
        "core": {"responsibility": "Neutral facts", "forbidden_imports": ["adapter"]},
        "adapter": {"responsibility": "Language interpretation", "forbidden_imports": []},
    },
    "exceptions": [],
}
FILES = {
    "src/widget/core/__init__.py": "",
    "src/widget/core/model.py": "class Model:\n    pass\n",
    "src/widget/adapter/__init__.py": "",
    "src/widget/adapter/parser.py": "from widget.core.model import Model\n",
    "tests/test_model.py": "def test_model():\n    assert True\n",
    "pyproject.toml": "[project]\nname = 'widget'\n",
}


def inventory(files=None, **kwargs):
    selected = FILES if files is None else files
    return analyze_architecture_inventory(
        SNAPSHOT, list(selected), selected, ROLE_POLICY, **kwargs
    )


class ArchitectureInventoryV01Tests(unittest.TestCase):
    def test_deterministic_source_hashes_and_real_tree(self) -> None:
        a = inventory()
        b = inventory(dict(reversed(list(FILES.items()))))
        self.assertEqual(a, b)
        self.assertEqual(a["coverage"]["tracked_total"], len(FILES))
        self.assertEqual(a["coverage"]["read"], len(FILES))
        self.assertEqual(a["coverage"]["parsed"], 0)
        self.assertEqual(a["status"], "EVIDENCE_ONLY")
        by_path = {item["path"]: item for item in a["files"]}
        self.assertEqual(by_path["src/widget/core/model.py"]["source_sha256"],
                         sha256(FILES["src/widget/core/model.py"].encode()).hexdigest())
        self.assertEqual(by_path["src/widget/core/model.py"]["ownership_class"],
                         "POLICY_DECLARED")
        self.assertEqual(a["package_metadata_paths"], ["pyproject.toml"])
        dirs = {item["path"]: item for item in a["directories"]}
        self.assertEqual(dirs["src/widget"]["descendant_files"], 4)
        self.assertEqual(dirs["src/widget"]["children"],
                         ["src/widget/adapter", "src/widget/core"])
        self.assertEqual(a["language_coverage"]["python"]["parser_status"], "NOT_EVALUATED")
        self.assertNotIn("question_opportunities", a)

    def test_missing_failed_excluded_and_generated_are_counted(self) -> None:
        paths = [*FILES, "src/widget/core/vanished.py", "src/widget/adapter/broken.rs",
                 "src/widget/core/skip.py"]
        report = analyze_architecture_inventory(
            SNAPSHOT, paths, FILES, ROLE_POLICY,
            failed_paths=["src/widget/adapter/broken.rs"],
            excluded_paths=["src/widget/core/skip.py"],
            generated_paths=["src/widget/adapter/parser.py"],
        )
        self.assertEqual(report["status"], "INCOMPLETE")
        self.assertEqual(report["coverage"]["tracked_total"], 9)
        self.assertEqual(report["coverage"]["read"], 6)
        self.assertEqual(report["coverage"]["missing"], 1)
        self.assertEqual(report["coverage"]["failed"], 1)
        self.assertEqual(report["coverage"]["excluded"], 1)
        self.assertEqual(report["coverage"]["generated"], 1)
        self.assertEqual(report["unknown_reasons"]["MISSING"], 1)
        self.assertEqual(report["language_coverage"]["rust"]["parser_status"], "NOT_EVALUATED")

    def test_symlink_is_not_followed_and_empty_package_is_observed(self) -> None:
        paths = [*FILES, "src/widget/core/link.py", "src/widget/adapter/empty/__init__.py"]
        sources = {**FILES, "src/widget/adapter/empty/__init__.py": ""}
        result = analyze_architecture_inventory(
            SNAPSHOT, paths, sources, ROLE_POLICY,
            symlink_paths=["src/widget/core/link.py"],
        )
        by_path = {item["path"]: item for item in result["files"]}
        self.assertIsNone(by_path["src/widget/core/link.py"]["source_sha256"])
        self.assertEqual(by_path["src/widget/core/link.py"]["read_state"],
                         "SYMLINK_NOT_FOLLOWED")
        packages = {p["path"]: p for p in result["packages"]}
        self.assertTrue(packages["src/widget/adapter/empty"]["no_other_python_modules"])
        self.assertEqual(result["coverage"]["symlink_not_followed"], 1)

    def test_name_hints_are_proxies_and_ambiguity_is_visible(self) -> None:
        rules = [{"domain": "alpha", "pattern": r"test_model\.py$"},
                 {"domain": "beta", "pattern": r"test_.*\.py$"}]
        result = inventory(name_hint_rules=rules)
        by_path = {item["path"]: item for item in result["files"]}
        self.assertEqual(by_path["tests/test_model.py"]["ownership_class"], "AMBIGUOUS")
        self.assertEqual(by_path["tests/test_model.py"]["evidence_class"], "PROXY_INFERENCE")
        self.assertEqual(by_path["src/widget/core/model.py"]["ownership_class"],
                         "POLICY_DECLARED")
        self.assertNotEqual(result["status"], "PASS")

    def test_unrelated_renamed_repository_has_no_hardcoded_domain(self) -> None:
        renamed = {p.replace("widget", "garden").replace("core", "soil")
                   .replace("adapter", "plant"): content for p, content in FILES.items()}
        policy = deepcopy(ROLE_POLICY)
        policy["scope"] = "src/garden"
        policy["roles"] = {
            "soil": {"responsibility": "Facts", "forbidden_imports": ["plant"]},
            "plant": {"responsibility": "Interpretation", "forbidden_imports": []},
        }
        result = analyze_architecture_inventory(SNAPSHOT, renamed, renamed, policy)
        self.assertEqual(result["coverage"]["read"], len(renamed))
        self.assertEqual(result["source_scope"], "src/garden")
        self.assertEqual(result["status"], "EVIDENCE_ONLY")

    def test_invalid_paths_and_snapshot_fail_closed(self) -> None:
        for bad in ("../escape.py", "/absolute.py", "src//double.py",
                    "src/widget/../escape.py", "src/widget/bad\nname.py",
                    "src/widget/name:stream.py", "src/widget/trailing./x.py"):
            with self.subTest(bad=repr(bad)):
                with self.assertRaises(ArchitectureInventoryError):
                    analyze_architecture_inventory(
                        SNAPSHOT, [*FILES, bad], FILES, ROLE_POLICY
                    )
        with self.assertRaises(ArchitectureInventoryError):
            analyze_architecture_inventory("main", FILES, FILES, ROLE_POLICY)
        with self.assertRaises(ArchitectureInventoryError):
            analyze_architecture_inventory(SNAPSHOT, [*FILES, "README.md"], FILES,
                                           ROLE_POLICY, excluded_paths=["not-tracked"])
        with self.assertRaises(ArchitectureInventoryError):
            analyze_architecture_inventory(SNAPSHOT, [*FILES, *FILES], FILES, ROLE_POLICY)

    def test_invalid_role_policy_and_overlap_fail_closed(self) -> None:
        policy = deepcopy(ROLE_POLICY)
        policy["roles"]["core"]["forbidden_imports"] = ["not_a_role"]
        with self.assertRaises(ArchitectureInventoryError):
            analyze_architecture_inventory(SNAPSHOT, FILES, FILES, policy)
        with self.assertRaises(ArchitectureInventoryError):
            inventory(name_hint_rules=[{"domain": "a", "pattern": "("}])
        with self.assertRaises(ArchitectureInventoryError):
            analyze_architecture_inventory(
                SNAPSHOT, [*FILES, "src/widget/core/bad.py"], FILES,
                ROLE_POLICY, excluded_paths=["src/widget/core/bad.py"],
                failed_paths=["src/widget/core/bad.py"],
            )
        with self.assertRaises(ArchitectureInventoryError):
            inventory(excluded_paths=["src/widget/core/model.py"])

    def test_versioned_json_schema_accepts_real_result_and_rejects_false_pass(self) -> None:
        schema = json.loads(
            (ROOT / "contracts/qa/architecture-inventory-v0.1.schema.json").read_text()
        )
        Draft202012Validator.check_schema(schema)
        report = inventory()
        Draft202012Validator(schema).validate(report)
        invalid = deepcopy(report)
        invalid["status"] = "PASS"
        with self.assertRaises(Exception):
            Draft202012Validator(schema).validate(invalid)
        invalid = deepcopy(report)
        invalid["files"][0]["parser_status"] = "SUPPORTED_RUNTIME"
        with self.assertRaises(Exception):
            Draft202012Validator(schema).validate(invalid)

    def test_actual_codeqa_head_tree_and_role_witnesses(self) -> None:
        """CI integration: enumerate real tracked paths, not a filename mock."""
        git = lambda *args: subprocess.run(
            ["git", *args], cwd=ROOT, check=True, capture_output=True
        ).stdout
        head = git("rev-parse", "HEAD").decode().strip()
        entries = git("ls-files", "--stage", "-z").split(b"\0")
        paths = []
        symlinks = []
        for entry in entries:
            if not entry:
                continue
            mode_and_oid, raw_path = entry.split(b"\t", 1)
            mode = mode_and_oid.split(b" ")[0]
            path = raw_path.decode("utf-8")
            paths.append(path)
            if mode in (b"120000", b"160000"):
                symlinks.append(path)
        reader = GitReader(ROOT)
        sources = {p: reader.read_file(head, p) for p in paths if p not in symlinks}
        policy = json.loads((ROOT / "profiles/semantic-directory-roles-v0.1.json").read_text())
        report = analyze_architecture_inventory(
            head, paths, sources, policy, symlink_paths=symlinks
        )
        self.assertEqual(report["source_identity"]["repository_commit_sha"], head)
        self.assertEqual(report["coverage"]["tracked_total"], len(paths))
        self.assertEqual(report["coverage"]["read"] + len(symlinks), len(paths))
        self.assertEqual(report["coverage"]["parsed"], 0)
        directory_names = {item["path"] for item in report["directories"]}
        self.assertTrue({"src/codeqa/core", "src/codeqa/adapters",
                         "src/codeqa/evaluation", "src/codeqa/pipeline",
                         "contracts", "fixtures", "tests"} <= directory_names)
        role_files = [item for item in report["files"]
                      if item["path"].startswith("src/codeqa/core/")]
        self.assertTrue(role_files)
        self.assertTrue(all(item["ownership_class"] == "POLICY_DECLARED"
                            for item in role_files))
        self.assertEqual(report["package_metadata_paths"], ["pyproject.toml"])


if __name__ == "__main__":
    unittest.main()
