#!/usr/bin/env python3
"""Exercise actual installed wheel against corrupted *real* resource bundle."""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile

from codeqa.infrastructure.resource_bundle import (
    ResourceBundleError, unpack_verified_resource_bundle,
)
from codeqa.infrastructure.resources import ResourceRegistry, ResourceResolutionError


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--bundle", type=Path, required=True)
    p.add_argument("--version", required=True)
    p.add_argument("--source-revision", required=True)
    args = p.parse_args()
    with ZipFile(args.bundle) as original:
        content = {name: original.read(name) for name in original.namelist()}
    manifest = json.loads(content["RESOURCE_MANIFEST.json"])
    cases = []
    cases.append(("wrong-version", {**manifest, "version": "0.0.0-invalid"}, dict(content)))
    cases.append(("wrong-source", {**manifest, "source_revision": "0" * 40}, dict(content)))
    damaged = dict(content)
    target = next(k for k in manifest["files_sha256"] if k != "pyproject.toml")
    damaged[target] += b"tampered"
    cases.append(("content-tamper", manifest, damaged))
    missing = dict(content)
    missing.pop(target)
    cases.append(("missing-registered-file", manifest, missing))
    extra = dict(content)
    extra["profiles/not-registered.json"] = b"{}"
    cases.append(("extra-unregistered-file", manifest, extra))
    with TemporaryDirectory(prefix="codeqa-negative-consumer-") as tmp:
        for index, (label, changed_manifest, files) in enumerate(cases):
            files["RESOURCE_MANIFEST.json"] = json.dumps(changed_manifest).encode()
            archive = Path(tmp) / f"{index}.zip"
            with ZipFile(archive, "w") as z:
                for name, payload in files.items():
                    z.writestr(name, payload)
            try:
                unpack_verified_resource_bundle(
                    archive, Path(tmp) / f"extract-{index}",
                    version=args.version, source_revision=args.source_revision,
                )
            except ResourceBundleError:
                continue
            raise SystemExit("PACKAGE_NEGATIVE_SMOKE=FAIL " + label)
        # Reuse the real, verified installed bundle: the registry must not
        # treat arbitrary consumer names as discoverable resource IDs.
        installed_root = Path(tmp) / "validated-resource-root"
        unpack_verified_resource_bundle(
            args.bundle, installed_root,
            version=args.version, source_revision=args.source_revision,
        )
        try:
            ResourceRegistry(installed_root).load_json("unknown_profile")
        except ResourceResolutionError:
            pass
        else:
            raise SystemExit("PACKAGE_NEGATIVE_SMOKE=FAIL unknown-profile")
    print("PACKAGE_NEGATIVE_SMOKE=PASS cases=", len(cases) + 1)


if __name__ == "__main__":
    main()
