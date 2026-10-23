#!/usr/bin/env python3
"""Validate only codeQA's branch-delete request manifest; Samuel owns deletion."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


_SHA = re.compile(r"[0-9a-f]{40}\Z")
_BRANCH = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/-]*\Z")
_MAX_TARGETS = 50


def validate_request(document: object) -> list[dict[str, str]]:
    """Return a bounded, checked GitHub Actions matrix include-list."""
    if not isinstance(document, dict) or set(document) != {"targets"}:
        raise ValueError("request must contain exactly targets")
    items = document["targets"]
    if not isinstance(items, list) or len(items) > _MAX_TARGETS:
        raise ValueError("targets must be a list of at most 50 entries")
    result: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, dict) or set(item) != {"branch", "expected_sha"}:
            raise ValueError("each target requires exactly branch and expected_sha")
        branch = item["branch"]
        sha = item["expected_sha"]
        if not isinstance(branch, str) or _BRANCH.fullmatch(branch) is None:
            raise ValueError("invalid branch name")
        segments = branch.split("/")
        if (
            branch == "main" or branch in seen or
            branch.endswith((".lock", ".")) or
            any(seg in ("", ".", "..") or seg.startswith(".") for seg in segments) or
            ".." in branch or "@{" in branch
        ):
            raise ValueError("default, duplicate or unsafe branch target")
        if not isinstance(sha, str) or _SHA.fullmatch(sha) is None:
            raise ValueError("expected_sha must be exact lowercase 40-hex")
        seen.add(branch)
        result.append({"branch": branch, "expected_sha": sha})
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--github-output", type=Path, required=True)
    args = parser.parse_args()
    document = json.loads(args.request.read_text(encoding="utf-8"))
    targets = validate_request(document)
    matrix = json.dumps({"include": targets}, separators=(",", ":"))
    with args.github_output.open("a", encoding="utf-8") as out:
        out.write(f"matrix={matrix}\n")
        out.write(f"has_targets={'true' if targets else 'false'}\n")
    print(f"CODEQA_BRANCH_DELETE_REQUEST=PASS count={len(targets)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
