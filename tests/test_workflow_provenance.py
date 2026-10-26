"""Git tracked SHA and retirement negative controls for workflow governance."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from codeqa.governance.workflow_catalog import WorkflowCatalogError
from codeqa.governance.workflow_provenance import (
    audit_workflow_provenance, validate_workflow_provenance,
)
from codeqa.infrastructure.git import GitReader

ROOT = Path(__file__).resolve().parents[1]


class WorkflowProvenanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads((ROOT / "docs/workflow-provenance-v0.1.json").read_text())
        cls.files = {
            p: (ROOT / p).read_text()
            for p in GitReader(ROOT).tracked_paths()
            if p.startswith(".github/workflows/") and p.endswith((".yml", ".yaml"))
        }
        cls.sha = cls.manifest["source_main_sha"]

    def verify(self, manifest=None, sources=None):
        validate_workflow_provenance(
            self.manifest if manifest is None else manifest,
            self.files if sources is None else sources, main_sha=self.sha,
        )

    def test_real_git_blob_manifest(self):
        audit_workflow_provenance(ROOT)
        self.assertEqual(len(self.manifest["workflows"]), len(self.files))

    def test_modified_workflow_rejected(self):
        src = dict(self.files)
        key = ".github/workflows/self-audit.yml"
        src[key] += "\n# drift\n"
        with self.assertRaisesRegex(WorkflowCatalogError, "drift"):
            self.verify(sources=src)

    def test_deleted_or_new_workflow_rejected(self):
        src = dict(self.files)
        src.pop(".github/workflows/self-audit.yml")
        with self.assertRaises(WorkflowCatalogError):
            self.verify(sources=src)
        src = dict(self.files)
        src[".github/workflows/new.yml"] = "name: new\n"
        with self.assertRaises(WorkflowCatalogError):
            self.verify(sources=src)

    def test_forged_blob_sha_rejected(self):
        m = deepcopy(self.manifest)
        m["workflows"][0]["blob_sha"] = "0"*40
        with self.assertRaises(WorkflowCatalogError):
            self.verify(m)

    def test_retirement_policy_cannot_be_automatic(self):
        m = deepcopy(self.manifest)
        m["retirement_policy"] = "AUTO_DELETE"
        with self.assertRaises(WorkflowCatalogError):
            self.verify(m)

    def test_duplicate_entry_rejected(self):
        m = deepcopy(self.manifest)
        m["workflows"].append(deepcopy(m["workflows"][0]))
        with self.assertRaises(WorkflowCatalogError):
            self.verify(m)


if __name__ == "__main__":
    unittest.main()
