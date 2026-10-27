"""Read-only Git blob evidence for #124 workflow governance."""
from __future__ import annotations

from hashlib import sha1
import json
from pathlib import Path
import re
from typing import Any, Mapping

from codeqa.governance.workflow_catalog import WorkflowCatalogError
from codeqa.infrastructure.git import GitReader


def validate_workflow_provenance(manifest: Mapping[str, Any], sources: Mapping[str, str],
                                 *, main_sha: str) -> None:
    if not isinstance(manifest, Mapping) or set(manifest) != {
        "version", "source_main_sha", "meaning", "retirement_policy", "workflows"
    } or manifest["version"] != "0.1" or manifest["source_main_sha"] != main_sha:
        raise WorkflowCatalogError("unmatched workflow source revision")
    if (not isinstance(main_sha, str) or not re.fullmatch(r"[0-9a-f]{40}", main_sha)
            or manifest["meaning"] != "GIT_BLOB_IDENTITY_NOT_CHECK_RUN_VERIFICATION"
            or manifest["retirement_policy"] !=
            "HUMAN_REVIEW_REQUIRED_PRESERVE_PINNED_EVIDENCE"):
        raise WorkflowCatalogError("unsupported provenance or retirement authority")
    rows = manifest["workflows"]
    if not isinstance(rows, list):
        raise WorkflowCatalogError("missing workflow provenance")
    observed = set()
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"path", "blob_sha"}:
            raise WorkflowCatalogError("invalid workflow identity")
        path, digest = row["path"], row["blob_sha"]
        if (not isinstance(path, str) or
                not re.fullmatch(r"\.github/workflows/[a-z0-9-]+\.ya?ml", path)
                or path in observed or path not in sources
                or not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{40}", digest)):
            raise WorkflowCatalogError("missing or duplicate Git blob source witness")
        observed.add(path)
        content = sources[path]
        if not isinstance(content, str):
            raise WorkflowCatalogError("non-text workflow source")
        data = content.encode("utf-8")
        actual = sha1(f"blob {len(data)}\0".encode("ascii") + data).hexdigest()
        if actual != digest:
            raise WorkflowCatalogError("workflow Git blob SHA drift: " + path)
    if observed != set(sources):
        raise WorkflowCatalogError("unclassified or missing workflow provenance")


def audit_workflow_provenance(root: Path) -> None:
    root = Path(root)
    main_catalog = json.loads((root / "docs/workflow-catalog-v0.1.json").read_text())
    manifest = json.loads((root / "docs/workflow-provenance-v0.1.json").read_text())
    paths = [p for p in GitReader(root).tracked_paths()
             if p.startswith(".github/workflows/") and p.endswith((".yml", ".yaml"))]
    sources = {path: (root / path).read_text(encoding="utf-8") for path in paths}
    validate_workflow_provenance(
        manifest, sources, main_sha=main_catalog["source_main_sha"],
    )


if __name__ == "__main__":
    audit_workflow_provenance(Path(__file__).resolve().parents[3])
    print("workflow Git blob provenance: source verified, runtime NOT_EVALUATED")
