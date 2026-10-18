"""Behavior and misuse tests for ResourceRegistry (no external dependencies)."""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest


from codeqa.infrastructure.resources import (
    ResourceRegistry, ResourceResolutionError, parse_json, parse_registry,
)


class ResourceRegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self._write_registry("profiles/first.json")
        self._write_resource("profiles/first.json", {"name": "initial"})

    def _write_registry(self, resource_path: str) -> None:
        # JSON quoting also produces valid TOML basic strings for these test paths.
        (self.root / "pyproject.toml").write_text(
            "[tool.codeqa.resources]\n"
            + "repository_layout = " + json.dumps(resource_path) + "\n",
            encoding="utf-8",
        )

    def _write_resource(self, relative: str, payload: object) -> None:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")

    def test_resolves_logical_id(self) -> None:
        self.assertEqual(
            ResourceRegistry(self.root).load_json("repository_layout"),
            {"name": "initial"},
        )

    def test_policy_move_only_requires_registry_change(self) -> None:
        registry = ResourceRegistry(self.root)
        old_path = self.root / "profiles/first.json"
        new_path = self.root / "contracts/nested/policy.json"
        new_path.parent.mkdir(parents=True)
        old_path.rename(new_path)
        self._write_registry("contracts/nested/policy.json")
        self.assertEqual(registry.load_json("repository_layout"), {"name": "initial"})

    def test_unknown_id_fails_closed(self) -> None:
        with self.assertRaises(ResourceResolutionError):
            ResourceRegistry(self.root).load_json("not_registered")

    def test_missing_file_fails_closed(self) -> None:
        self._write_registry("profiles/missing.json")
        with self.assertRaises(ResourceResolutionError):
            ResourceRegistry(self.root).load_json("repository_layout")

    def test_missing_registry_fails_closed(self) -> None:
        (self.root / "pyproject.toml").write_text("[project]\nname='demo'\n")
        with self.assertRaises(ResourceResolutionError):
            ResourceRegistry(self.root).resolve("repository_layout")

    def test_malformed_registry_fails_closed(self) -> None:
        (self.root / "pyproject.toml").write_text("[bad\n")
        with self.assertRaises(ResourceResolutionError):
            ResourceRegistry(self.root).resolve("repository_layout")

    def test_malformed_json_fails_closed(self) -> None:
        (self.root / "profiles/first.json").write_text("{bad json")
        with self.assertRaises(ResourceResolutionError):
            ResourceRegistry(self.root).load_json("repository_layout")

    def test_invalid_resource_id_fails_closed(self) -> None:
        for resource_id in ("", "../repository_layout", "Repository-Layout", None):
            with self.subTest(resource_id=resource_id):
                with self.assertRaises(ResourceResolutionError):
                    ResourceRegistry(self.root).resolve(resource_id)

    def test_unsafe_paths_are_rejected(self) -> None:
        for path in (
            "../other/policy.json",
            "/etc/passwd",
            "profiles/../../etc/passwd",
            "profiles//first.json",
            "profiles/./first.json",
            "C:\\outside\\policy.json",
            "",
        ):
            with self.subTest(path=path):
                self._write_registry(path)
                with self.assertRaises(ResourceResolutionError):
                    ResourceRegistry(self.root).resolve("repository_layout")

    def test_symbolic_link_cannot_escape_repository(self) -> None:
        with tempfile.TemporaryDirectory() as outside:
            target = Path(outside) / "policy.json"
            target.write_text('{"unsafe": true}')
            link = self.root / "profiles/linked.json"
            try:
                link.symlink_to(target)
            except (NotImplementedError, OSError):
                self.skipTest("symlinks unavailable on this platform")
            self._write_registry("profiles/linked.json")
            with self.assertRaises(ResourceResolutionError):
                ResourceRegistry(self.root).resolve("repository_layout")

    def test_shared_registry_and_json_parsing(self) -> None:
        registry = parse_registry(b'[tool.codeqa.resources]\\nrepository_layout = "policies/x.json"\\n')
        self.assertEqual(registry["tool"]["codeqa"]["resources"]["repository_layout"], "policies/x.json")
        self.assertEqual(parse_json(b'{"value": 42}', "example"), {"value": 42})

    def test_invalid_resource_parsers_fail_closed(self) -> None:
        with self.assertRaises(ResourceResolutionError):
            parse_registry(b'[broken')
        with self.assertRaises(ResourceResolutionError):
            parse_json(b'{bad', "example")


if __name__ == "__main__":
    unittest.main()
