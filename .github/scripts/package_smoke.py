#!/usr/bin/env python3
"""Run codeQA from an *installed* Python distribution outside the checkout."""
from __future__ import annotations

import argparse
from importlib.metadata import version
from pathlib import Path
from tempfile import TemporaryDirectory


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--version", required=True)
    args = parser.parse_args()

    import codeqa
    from codeqa.infrastructure.resources import ResourceRegistry
    from codeqa.infrastructure.resource_bundle import ResourceBundleError, unpack_verified_resource_bundle
    from codeqa.pipeline.python import analyze_python

    installed = Path(codeqa.__file__).resolve()
    checkout = args.source_root.resolve()
    if installed.is_relative_to(checkout):
        raise SystemExit("PACKAGE_SMOKE=FAIL imported codeqa from source checkout")
    if version("codeqa") != args.version:
        raise SystemExit("PACKAGE_SMOKE=FAIL distribution metadata mismatch")

    with TemporaryDirectory(prefix="codeqa-package-resources-") as tmpdir:
        dest = Path(tmpdir)
        try:
            manifest = unpack_verified_resource_bundle(
                args.bundle, dest, version=args.version,
                source_revision=args.source_revision,
            )
        except ResourceBundleError as exc:
            raise SystemExit("PACKAGE_SMOKE=FAIL " + str(exc)) from exc
        hashes = manifest["files_sha256"]

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
