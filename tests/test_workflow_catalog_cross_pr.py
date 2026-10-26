"""Regression for concurrent domain-inventory workflow evolution."""
import json
from pathlib import Path
import unittest
from codeqa.governance.workflow_catalog import WorkflowCatalogError, validate_workflow_catalog
from codeqa.infrastructure.git import GitReader

ROOT = Path(__file__).resolve().parents[1]


class WorkflowCrossPRTests(unittest.TestCase):
    def test_extra_self_audit_upload_requires_catalog_update(self):
        catalog = json.loads((ROOT / "docs/workflow-catalog-v0.1.json").read_text())
        paths = GitReader(ROOT).tracked_paths()
        sources = {
            path: (ROOT / path).read_text()
            for path in paths
            if path.startswith(".github/workflows/") and path.endswith((".yml", ".yaml"))
        }
        path = ".github/workflows/self-audit.yml"
        self.assertEqual(
            next(item for item in catalog["workflows"] if item["path"] == path)["artifact_upload_count"],
            sources[path].count("uses: actions/upload-artifact@"),
        )
        sources[path] += "\n      - name: Store domain inventory\n        uses: actions/upload-artifact@v4\n"
        with self.assertRaisesRegex(WorkflowCatalogError, "artifact upload count drift"):
            validate_workflow_catalog(catalog, paths, sources)


if __name__ == "__main__":
    unittest.main()
