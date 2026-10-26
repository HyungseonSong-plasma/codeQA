"""Source-level negative control for default Python Naming isolation."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import codeqa.governance.support_surface as surface

ROOT = Path(__file__).resolve().parents[1]


class DefaultNamingImportBoundaryTests(unittest.TestCase):
    def test_static_naming_import_does_not_become_default(self):
        manifest = json.loads((ROOT / "docs/support-surface-v0.1.json").read_text())
        real_resolve = surface._path
        with TemporaryDirectory() as temporary:
            replacement = Path(temporary) / "python.py"
            replacement.write_text(
                "from codeqa.evaluation.naming import evaluate_naming\n"
                "def analyze_python(): pass\n",
                encoding="utf-8",
            )
            def resolve(root, name):
                if name == "src/codeqa/pipeline/python.py":
                    return replacement
                return real_resolve(root, name)
            with patch.object(surface, "_path", side_effect=resolve):
                with self.assertRaisesRegex(surface.SupportSurfaceError, "imports opt-in Naming"):
                    surface.audit_support_surface(ROOT, manifest)


if __name__ == "__main__":
    unittest.main()
