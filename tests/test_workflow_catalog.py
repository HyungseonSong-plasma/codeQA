"""Exact tracked workflow inventory and negative authority controls (#124)."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import unittest

from codeqa.governance.workflow_catalog import (
    WorkflowCatalogError, audit_workflow_catalog, validate_workflow_catalog,
)
from codeqa.infrastructure.git import GitReader


ROOT = Path(__file__).resolve().parents[1]


class WorkflowCatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads((ROOT / "docs/workflow-catalog-v0.1.json").read_text())
        cls.paths = GitReader(ROOT).tracked_paths()
        cls.sources = {
            path: (ROOT / path).read_text()
            for path in cls.paths if path.startswith(".github/workflows/") and path.endswith((".yml", ".yaml"))
        }

    def test_live_tracked_catalog_matches_exact_workflows(self):
        audit_workflow_catalog(ROOT)

    def _bad(self, mutate, paths=None, sources=None):
        data = deepcopy(self.manifest)
        mutate(data)
        with self.assertRaises(WorkflowCatalogError):
            validate_workflow_catalog(data, self.paths if paths is None else paths,
                                      self.sources if sources is None else sources)

    def test_unclassified_new_workflow_rejected(self):
        new_path = ".github/workflows/extra.yml"
        with self.assertRaises(WorkflowCatalogError):
            validate_workflow_catalog(self.manifest, [*self.paths, new_path],
                                      {**self.sources, new_path: "name: extra\non:\n  push:\n"})

    def test_stale_deleted_workflow_rejected(self):
        self._bad(lambda d: None, sources={k:v for k,v in self.sources.items() if not k.endswith("/layout.yml")})

    def test_invented_required_check_rejected(self):
        self._bad(lambda d: next(e for e in d["workflows"] if e["path"].endswith("self-audit.yml")).update(
            required_check="self-audit", required_status="OBSERVED_REQUIRED_BY_RULESET_25360323"
        ))

    def test_ruleset_identity_cannot_be_forged(self):
        self._bad(lambda d: d["ruleset"].update(required_check_context="self-audit"))

    def test_duplicate_required_layout_context_rejected(self):
        sources = dict(self.sources)
        path = ".github/workflows/layout.yml"
        sources[path] += (
            "\n  another_layout:\n"
            "    name: layout\n"
            "    runs-on: ubuntu-latest\n"
            "    steps: []\n"
        )
        self._bad(lambda d: None, sources=sources)

    def test_other_workflow_cannot_shadow_required_context_by_job_name(self):
        sources = dict(self.sources)
        path = ".github/workflows/self-audit.yml"
        sources[path] += (
            "\n  shadow_layout:\n"
            "    name: layout\n"
            "    runs-on: ubuntu-latest\n"
            "    steps: []\n"
        )
        self._bad(lambda d: None, sources=sources)

    def test_other_workflow_cannot_shadow_required_context_by_job_id(self):
        sources = dict(self.sources)
        path = ".github/workflows/self-audit.yml"
        sources[path] += (
            "\n  layout:\n"
            "    runs-on: ubuntu-latest\n"
            "    steps: []\n"
        )
        self._bad(lambda d: None, sources=sources)

    def test_required_job_cannot_be_conditional_or_continue_on_error(self):
        path = ".github/workflows/layout.yml"
        for injection in ("    if: false\n", "    needs: missing_job\n",
                          "    continue-on-error: true\n"):
            with self.subTest(injection=injection):
                sources = dict(self.sources)
                sources[path] = sources[path].replace(
                    "    name: layout\n", "    name: layout\n" + injection
                )
                self._bad(lambda d: None, sources=sources)

    def test_required_pr_event_cannot_be_filtered(self):
        sources = dict(self.sources)
        path = ".github/workflows/layout.yml"
        sources[path] = sources[path].replace(
            "  pull_request:\n", "  pull_request:\n    branches: [not-main]\n"
        )
        self._bad(lambda d: None, sources=sources)

    def test_required_checkout_cannot_be_replaced_or_redirected(self):
        path = ".github/workflows/layout.yml"
        for extra in ("        uses: attacker/checkout@v1\n",
                      "          ref: unreviewed-branch\n",
                      "          repository: other/untrusted\n",
                      "          path: elsewhere\n"):
            with self.subTest(extra=extra):
                sources = dict(self.sources)
                sources[path] = sources[path].replace(
                    "          fetch-depth: 0\n",
                    "          fetch-depth: 0\n" + extra,
                )
                self._bad(lambda d: None, sources=sources)

    def test_required_guard_commands_cannot_be_removed(self):
        sources = dict(self.sources)
        path = ".github/workflows/layout.yml"
        sources[path] = sources[path].replace(
            "python3 -m unittest discover -s tests", "echo skipped-tests"
        )
        self._bad(lambda d: None, sources=sources)

    def test_required_steps_cannot_be_disabled_individually(self):
        path = ".github/workflows/layout.yml"
        for step_name in (
            "Verify CCG Core, contracts, layout and frozen policy tests",
            "Evaluate directory roles and versioned semantic architecture evidence",
        ):
            with self.subTest(step_name=step_name):
                sources = dict(self.sources)
                sources[path] = sources[path].replace(
                    "      - name: " + step_name + "\n",
                    "      - name: " + step_name + "\n        if: false\n",
                )
                self._bad(lambda d: None, sources=sources)

    def test_required_commands_must_execute_not_echo_or_ignore_errors(self):
        path = ".github/workflows/layout.yml"
        command = "python3 -m unittest discover -s tests -p 'test_*.py' -v"
        for altered in ("echo " + command, command + " || true", "# " + command):
            with self.subTest(altered=altered):
                sources = dict(self.sources)
                sources[path] = sources[path].replace(
                    "run: " + command, "run: " + altered,
                )
                self._bad(lambda d: None, sources=sources)

    def test_frozen_policy_step_cannot_be_skipped_or_replaced_by_echo(self):
        path = ".github/workflows/layout.yml"
        for original, replacement in (
            ("if: github.event_name == 'pull_request' || github.event_name == 'push'",
             "if: false"),
            ("python3 -m codeqa.governance.frozen_policy",
             "echo python3 -m codeqa.governance.frozen_policy"),
            ("--resource-id repository_layout", "--resource-id repository_layout || true"),
        ):
            with self.subTest(replacement=replacement):
                sources = dict(self.sources)
                sources[path] = sources[path].replace(original, replacement)
                self._bad(lambda d: None, sources=sources)

    def test_duplicate_required_step_label_rejected(self):
        path = ".github/workflows/layout.yml"
        sources = dict(self.sources)
        sources[path] = sources[path].replace(
            "      - name: Evaluate directory roles and versioned semantic architecture evidence\n",
            "      - name: Verify CCG Core, contracts, layout and frozen policy tests\n",
        )
        self._bad(lambda d: None, sources=sources)

    def test_artifact_upload_drift_rejected(self):
        self._bad(lambda d: next(e for e in d["workflows"] if e["path"].endswith("layout.yml")).update(
            artifact_upload_count=999
        ))

    def test_trigger_drift_rejected(self):
        self._bad(lambda d: next(e for e in d["workflows"] if e["path"].endswith("layout.yml")).update(
            trigger_events=["workflow_dispatch"]
        ))

    def test_retention_unverified_not_invented(self):
        self._bad(lambda d: next(e for e in d["workflows"] if e["path"].endswith("layout.yml")).update(
            retention_status="GUARANTEED_90_DAYS"
        ))

    def test_operational_workflow_not_product_quality_pass(self):
        self._bad(lambda d: next(e for e in d["workflows"] if e["path"].endswith("samuel-codeqa-issue-execute.yml")).update(
            artifact_authority="SCOPED_CI_ONLY"
        ))


if __name__ == "__main__":
    unittest.main()
