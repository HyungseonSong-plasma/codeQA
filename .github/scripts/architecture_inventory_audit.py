#!/usr/bin/env python3
"""Read-only exact-HEAD architecture B1 inventory artifact generator."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess

from codeqa.evaluation.architecture.inventory import analyze_architecture_inventory


def git(*args: str) -> bytes:
    return subprocess.run(
        ["git", *args], check=True, capture_output=True
    ).stdout


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    sha = git("rev-parse", "HEAD").decode("ascii").strip()
    records = git("ls-tree", "-rz", "HEAD").split(b"\0")
    paths: list[str] = []
    sources: dict[str, bytes] = {}
    symlinks: list[str] = []
    failed: list[str] = []
    for record in records:
        if not record:
            continue
        header, raw_path = record.split(b"\t", 1)
        mode, kind, _blob_sha = header.split(b" ")
        path = raw_path.decode("utf-8")
        paths.append(path)
        if mode == b"120000":
            symlinks.append(path)
        elif mode == b"160000" or kind != b"blob":
            failed.append(path)
        else:
            sources[path] = git("show", f"{sha}:{path}")
    policy = json.loads(
        git("show", f"{sha}:profiles/semantic-directory-roles-v0.1.json")
    )
    report = analyze_architecture_inventory(
        sha, paths, sources, policy, symlink_paths=symlinks, failed_paths=failed
    )
    args.output.write_text(
        json.dumps(report, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"ARCHITECTURE_INVENTORY_B1 head={sha} tracked={len(paths)} "
        f"read={report['coverage']['read']} status={report['status']} "
        f"artifact={args.output}"
    )


if __name__ == "__main__":
    main()
