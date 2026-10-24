"""The separate registered-resource artifact must be deterministic and safe."""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import runpy
from tempfile import TemporaryDirectory
import unittest
from zipfile import ZipFile


ROOT=Path(__file__).resolve().parents[1]
generate=runpy.run_path(
    str(ROOT / ".github/scripts/build_resource_bundle.py")
)["generate"]


class PackageResourceBundleTests(unittest.TestCase):
    def fixture(self, location: Path):
        (location / "profiles").mkdir()
        (location / "contracts").mkdir()
        (location / "profiles/example.json").write_text('{"version": 1}\n')
        (location / "contracts/sample.json").write_text('{"type": "object"}\n')
        (location / "pyproject.toml").write_text(
            '[project]\nname = "codeqa"\nversion = "0.2.0a1"\n'
            '[tool.codeqa.resources]\n'
            'policy = "profiles/example.json"\n'
            'schema = "contracts/sample.json"\n'
        )

    def test_manifest_matches_resource_bytes_and_is_deterministic(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp)
            self.fixture(root)
            one=root / "candidate-1.zip"
            two=root / "candidate-2.zip"
            sha="a"*40
            manifest=generate(root,one,sha)
            generate(root,two,sha)
            self.assertEqual(one.read_bytes(),two.read_bytes())
            self.assertEqual(manifest["source_revision"],sha)
            self.assertEqual(set(manifest["files_sha256"]),{
                "pyproject.toml","profiles/example.json","contracts/sample.json"})
            with ZipFile(one) as z:
                raw=json.loads(z.read("RESOURCE_MANIFEST.json"))
                self.assertEqual(raw,manifest)
                for name,expected in manifest["files_sha256"].items():
                    self.assertEqual(sha256(z.read(name)).hexdigest(),expected)

    def test_unsafe_or_missing_registered_path_is_rejected(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp)
            self.fixture(root)
            path=root / "pyproject.toml"
            original=path.read_text()
            for bad in ("../secret.json", "/etc/passwd",
                        "src/not-a-contract.json","contracts/../file.json"):
                with self.subTest(bad=bad):
                    path.write_text(original.replace(
                        'contracts/sample.json',bad))
                    with self.assertRaises(ValueError):
                        generate(root,root / "out.zip","a"*40)
            path.write_text(original)
            (root/"contracts/sample.json").unlink()
            with self.assertRaises(ValueError):
                generate(root,root/"out.zip","a"*40)

    def test_commit_id_must_be_exact(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp)
            self.fixture(root)
            for bad in ("main", "A"*40, "abc", ""):
                with self.subTest(bad=bad), self.assertRaises(ValueError):
                    generate(root,root/"out.zip",bad)


if __name__=="__main__":
    unittest.main()
