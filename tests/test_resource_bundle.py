"""Bundle integrity negatives without importing untrusted user source (#125)."""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest
from zipfile import ZipFile

from codeqa.infrastructure.resource_bundle import (
    ResourceBundleError, unpack_verified_resource_bundle,
)


VERSION = "0.2.0a1"
SHA = "a" * 40


def _files():
    registry = {"ccg_schema": "contracts/ccg.json", "mechanical_profile": "profiles/mechanical.json"}
    config = (
        '[project]\nname = "codeqa"\nversion = "' + VERSION + '"\n'
        '[tool.codeqa.resources]\nccg_schema = "contracts/ccg.json"\n'
        'mechanical_profile = "profiles/mechanical.json"\n'
    ).encode()
    return registry, {
        "pyproject.toml": config,
        "contracts/ccg.json": b'{"type":"object"}',
        "profiles/mechanical.json": b'{"max_function_lines": 60}',
    }


class ResourceBundleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.registry, self.files = _files()

    def bundle(self, *, manifest_change=None, files_change=None):
        files = dict(self.files)
        if files_change:
            files_change(files)
        manifest = {
            "schema_version": 1, "distribution": "codeqa-resource-bundle",
            "version": VERSION, "source_revision": SHA,
            "resources": self.registry,
            "files_sha256": {k: sha256(v).hexdigest() for k,v in files.items()},
        }
        if manifest_change:
            manifest_change(manifest)
        archive = self.root / "bundle.zip"
        with ZipFile(archive, "w") as z:
            for name, content in files.items():
                z.writestr(name, content)
            z.writestr("RESOURCE_MANIFEST.json", json.dumps(manifest))
        return archive

    def unpack(self, path, *, version=VERSION, sha=SHA):
        return unpack_verified_resource_bundle(
            path, self.root / "extracted", version=version, source_revision=sha,
        )

    def test_valid_exact_bundle_extracts_explicit_resource_root(self):
        result = self.unpack(self.bundle())
        self.assertEqual(result["source_revision"], SHA)
        self.assertTrue((self.root / "extracted/contracts/ccg.json").is_file())

    def test_wrong_version_fails_closed(self):
        with self.assertRaises(ResourceBundleError):
            self.unpack(self.bundle(), version="0.2.0a2")

    def test_wrong_source_revision_fails_closed(self):
        with self.assertRaises(ResourceBundleError):
            self.unpack(self.bundle(), sha="b" * 40)

    def test_tampered_content_hash_fails_closed(self):
        with self.assertRaises(ResourceBundleError):
            self.unpack(self.bundle(manifest_change=lambda m: m["files_sha256"].update(
                {"contracts/ccg.json": "0" * 64}
            )))

    def test_hash_consistent_but_malformed_json_resource_rejected(self):
        with self.assertRaisesRegex(ResourceBundleError, "malformed registered JSON"):
            self.unpack(self.bundle(files_change=lambda f: f.update({
                "contracts/ccg.json": b'{"type":'
            })))
        self.assertFalse((self.root / "extracted").exists())

    def test_hash_consistent_but_duplicate_json_keys_rejected(self):
        with self.assertRaisesRegex(ResourceBundleError, "duplicate JSON"):
            self.unpack(self.bundle(files_change=lambda f: f.update({
                "contracts/ccg.json": b'{"type":"object","type":"array"}'
            })))
        self.assertFalse((self.root / "extracted").exists())

    def test_hash_consistent_but_nonfinite_json_rejected(self):
        with self.assertRaisesRegex(ResourceBundleError, "non-finite registered JSON"):
            self.unpack(self.bundle(files_change=lambda f: f.update({
                "contracts/ccg.json": b'{"unsafe": NaN}'
            })))
        self.assertFalse((self.root / "extracted").exists())

    def test_missing_registered_file_fails_closed(self):
        with self.assertRaises(ResourceBundleError):
            self.unpack(self.bundle(files_change=lambda f: f.pop("profiles/mechanical.json")))

    def test_extra_unregistered_file_fails_closed(self):
        with self.assertRaises(ResourceBundleError):
            self.unpack(self.bundle(files_change=lambda f: f.update({"profiles/unknown.json": b"{}"})))

    def test_unsafe_registry_path_fails_closed(self):
        with self.assertRaises(ResourceBundleError):
            self.unpack(self.bundle(manifest_change=lambda m: m["resources"].update(
                {"ccg_schema": "../outside.json"}
            )))

    def test_control_character_archive_member_fails_closed(self):
        for bad in ("profiles/unsafe\n.json", "profiles/unsafe\t.json",
                    "profiles/unsafe\x7f.json"):
            with self.subTest(bad=repr(bad)):
                with self.assertRaisesRegex(ResourceBundleError, "unsafe archive member"):
                    self.unpack(self.bundle(files_change=lambda f: f.update({bad: b"{}"})))

    def test_control_character_registry_path_fails_closed(self):
        for bad in ("profiles/unsafe\n.json", "profiles/unsafe\r.json"):
            with self.subTest(bad=repr(bad)):
                with self.assertRaises(ResourceBundleError):
                    self.unpack(self.bundle(manifest_change=lambda m: m["resources"].update(
                        {"ccg_schema": bad}
                    )))

    def test_nonportable_archive_member_paths_rejected_before_extraction(self):
        for bad in ("profiles/file.json:stream", "profiles/CON.json",
                    "profiles/trailing .json.", "profiles/cafe\u0301.json"):
            with self.subTest(bad=repr(bad)):
                with self.assertRaisesRegex(ResourceBundleError, "unsafe archive member"):
                    self.unpack(self.bundle(files_change=lambda f: f.update({bad: b"{}"})))
                self.assertFalse((self.root / "extracted").exists())

    def test_case_insensitive_archive_alias_rejected_before_extraction(self):
        with self.assertRaisesRegex(ResourceBundleError, "portable archive path collision"):
            self.unpack(self.bundle(files_change=lambda f: f.update({
                "profiles/EXTRA.json": b"{}", "profiles/extra.json": b"{}",
            })))
        self.assertFalse((self.root / "extracted").exists())

    def test_wrong_registry_identity_fails_closed(self):
        with self.assertRaises(ResourceBundleError):
            self.unpack(self.bundle(manifest_change=lambda m: m["resources"].update(
                {"unregistered": "profiles/unknown.json"}
            )))

    def test_missing_manifest_fails_closed(self):
        archive = self.root / "empty.zip"
        with ZipFile(archive, "w") as z:
            z.writestr("pyproject.toml", self.files["pyproject.toml"])
        with self.assertRaises(ResourceBundleError):
            self.unpack(archive)

    def test_bad_source_sha_fails_closed(self):
        with self.assertRaises(ResourceBundleError):
            self.unpack(self.bundle(), sha="main")

    def test_symlinked_destination_is_rejected(self):
        with tempfile.TemporaryDirectory() as outside:
            link = self.root / "extracted"
            try:
                link.symlink_to(outside, target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("symlink creation unavailable")
            with self.assertRaises(ResourceBundleError):
                self.unpack(self.bundle())

    def test_destination_not_empty_fails_closed(self):
        target = self.root / "extracted"
        target.mkdir()
        (target / "old").write_text("x")
        with self.assertRaises(ResourceBundleError):
            self.unpack(self.bundle())


if __name__ == "__main__":
    unittest.main()
