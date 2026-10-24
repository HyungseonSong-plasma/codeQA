#!/usr/bin/env python3
"""Run codeQA from an *installed* Python distribution outside the checkout."""
from __future__ import annotations

import argparse
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory
from zipfile import ZipFile


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--version", required=True)
    args = parser.parse_args()

    import codeqa
    from codeqa.infrastructure.resources import ResourceRegistry
    from codeqa.pipeline.python import analyze_python

    installed = Path(codeqa.__file__).resolve()
    checkout = args.source_root.resolve()
    if installed.is_relative_to(checkout):
        raise SystemExit("PACKAGE_SMOKE=FAIL imported codeqa from source checkout")
    if version("codeqa") != args.version:
        raise SystemExit("PACKAGE_SMOKE=FAIL distribution metadata mismatch")

    with TemporaryDirectory(prefix="codeqa-package-resources-") as tmpdir:
        dest = Path(tmpdir)
        with ZipFile(args.bundle) as archive:
            names = archive.namelist()
            if len(set(names)) != len(names):
                raise SystemExit("PACKAGE_SMOKE=FAIL duplicate resource archive names")
            for name in names:
                p = PurePosixPath(name)
                if (p.is_absolute() or "\\" in name
                        or any(part in {"", ".", ".."} for part in name.split("/"))):
                    raise SystemExit("PACKAGE_SMOKE=FAIL unsafe archive path")
            if "RESOURCE_MANIFEST.json" not in names:
                raise SystemExit("PACKAGE_SMOKE=FAIL missing manifest")
            manifest = json.loads(archive.read("RESOURCE_MANIFEST.json"))
            if manifest["version"] != args.version:
                raise SystemExit("PACKAGE_SMOKE=FAIL resource bundle version mismatch")
            if manifest["source_revision"] != args.source_revision:
                raise SystemExit("PACKAGE_SMOKE=FAIL resource snapshot mismatch")
            hashes = manifest["files_sha256"]
            if set(names) != set(hashes) | {"RESOURCE_MANIFEST.json"}:
                raise SystemExit("PACKAGE_SMOKE=FAIL bundle content differs from manifest")
            if len(manifest["resources"]) < 2:
                raise SystemExit("PACKAGE_SMOKE=FAIL incomplete resource registry")
            for name, digest in hashes.items():
                data = archive.read(name)
                if sha256(data).hexdigest() != digest:
                    raise SystemExit("PACKAGE_SMOKE=FAIL bundled resource hash mismatch")
                out = dest.joinpath(*name.split("/"))
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_bytes(data)

        registry = ResourceRegistry(dest)
        schema = registry.load_json("ccg_schema")
        profile = registry.load_json("mechanical_profile")
        report = analyze_python(
            {"src/sample.py": "def hello():\n    return 1\n"},
            snapshot_id="package-smoke:v0.2",
            ccg_schema=schema, mechanical_profile=profile,
        )
        summary = report.summary_document()
        if not report.graph.nodes or summary["source"]["analyzed_files"] != 1:
            raise SystemExit("PACKAGE_SMOKE=FAIL no actual installed-package analysis")
        print("PACKAGE_SMOKE=PASS", installed, "node_count=", len(report.graph.nodes),
              "resource_count=", len(hashes), "version=", version("codeqa"))


if __name__ == "__main__":
    main()
