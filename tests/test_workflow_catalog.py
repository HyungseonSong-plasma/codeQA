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

    def test_required_guard_commands_cannot_be_removed(self):
        sources = dict(self.sources)
        path = ".github/workflows/layout.yml"
        sources[path] = sources[path].replace(
            "python3 -m unittest discover -s tests", "echo skipped-tests"
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
