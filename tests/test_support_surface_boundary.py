"""Review authority boundaries for the support-surface inventory."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from codeqa.governance.support_surface import (
    SupportSurfaceError, audit_support_surface, render_support_table,
)

ROOT = Path(__file__).resolve().parents[1]


class SupportSurfaceBoundaryTests(unittest.TestCase):
    def test_naming_stays_opt_in_when_readme_matches_manifest(self):
        manifest = json.loads((ROOT / "docs/support-surface-v0.1.json").read_text())
        readme = (ROOT / "README.md").read_text()
        altered = deepcopy(manifest)
        feature = next(f for f in altered["features"] if f["id"] == "python_naming_safe")
        feature["mode"] = "DEFAULT_SCOPED"
        feature["authority"] = "HEURISTIC_REVIEW"
        readme = readme.replace(render_support_table(manifest), render_support_table(altered))
        with self.assertRaises(SupportSurfaceError):
            audit_support_surface(ROOT, altered, readme=readme)


if __name__ == "__main__":
    unittest.main()
