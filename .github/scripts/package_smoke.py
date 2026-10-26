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
    from codeqa.pipeline.analysis_request import AnalysisOptions, AnalysisRequest, analyze_python_request, AnalysisRequestError

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
        requested = analyze_python_request(AnalysisRequest(
            sources={"src/sample.py": "def hello():\n    return 1\n"},
            snapshot_id="package-smoke:v0.2",
            ccg_schema=schema, mechanical_profile=profile,
            options=AnalysisOptions.from_mapping({"changed_paths": ["src/sample.py"]}),
        ))
        if (requested.analysis.graph.to_document() != report.graph.to_document()
                or requested.analysis.quality.to_document() != report.quality.to_document()
                or requested.companion_states["impact"] != "EXECUTED"
                or requested.companion_states["naming"] != "NOT_REQUESTED"
                or requested.companion_states["formal"] != "NOT_REQUESTED"):
            raise SystemExit("PACKAGE_SMOKE=FAIL opt-in request changed Mechanical or activated unsupported companions")
        authority_negative_count = 0
        for unsupported in ("naming", "formal", "external_gate"):
            for invalid in (True, 0, None, "", []):
                try:
                    AnalysisOptions.from_mapping({unsupported: invalid})
                except AnalysisRequestError:
                    authority_negative_count += 1
                else:
                    raise SystemExit(
                        "PACKAGE_REQUEST_SMOKE=FAIL unsupported/ambiguous authority: "
                        + unsupported + " value=" + repr(invalid)
                    )
        if authority_negative_count != 15:
            raise SystemExit("PACKAGE_REQUEST_SMOKE=FAIL missing negative cases")
        print("PACKAGE_REQUEST_SMOKE=PASS impact=EXECUTED naming/formal/external_gate=NOT_REQUESTED authority_negatives=15")

        print("PACKAGE_SMOKE=PASS", installed, "node_count=", len(report.graph.nodes),
              "resource_count=", len(hashes), "version=", version("codeqa"))


if __name__ == "__main__":
    main()
