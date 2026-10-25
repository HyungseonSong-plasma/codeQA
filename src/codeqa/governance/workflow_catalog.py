"""Read-only, exact-tracked-file workflow governance catalog audit (#124).

Does not infer live GitHub rulesets from YAML. The manifest's ruleset is a
dated independently read snapshot; CI checks internal consistency only.
"""
from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
import re
from typing import Any


class WorkflowCatalogError(ValueError):
    """Workflow inventory or asserted required authority is inconsistent."""


CATEGORIES = {"required", "conformance", "experimental", "operations"}
AUTHORITY = {
    "required": "SCOPED_CI_ONLY",
    "conformance": "SCOPED_CI_ONLY",
    "experimental": "INFORMATIONAL_ONLY",
    "operations": "OPERATIONAL_RECEIPT_ONLY",
}
ENTRY_KEYS = {
    "path", "category", "owner", "trigger_events", "required_check",
    "required_status", "artifact_upload_count", "artifact_authority",
    "retention_status",
}
REQUIRED_CONTEXT = "layout"
RULESET_ID = 25360323


def _events(text: str) -> list[str]:
    match = re.search(r"(?m)^on:\s*\n((?:[ \t]+.*\n|\s*\n)*)", text)
    if not match:
        raise WorkflowCatalogError("unrecognized workflow event syntax")
    events = re.findall(r"(?m)^  ([a-z_]+):", match.group(1))
    if not events or len(set(events)) != len(events):
        raise WorkflowCatalogError("missing or duplicate workflow triggers")
    return sorted(events)


def validate_workflow_catalog(
    manifest: Mapping[str, Any], tracked_paths: list[str],
    workflow_sources: Mapping[str, str],
) -> None:
    if not isinstance(manifest, Mapping) or set(manifest) != {
        "schema_version", "source_main_sha", "ruleset", "workflows"
    } or manifest["schema_version"] != "0.1":
        raise WorkflowCatalogError("invalid workflow catalog")
    if not re.fullmatch(r"[0-9a-f]{40}", manifest["source_main_sha"]):
        raise WorkflowCatalogError("missing source baseline SHA")
    ruleset = manifest["ruleset"]
    if not isinstance(ruleset, dict) or set(ruleset) != {
        "id", "name", "observed_date", "required_check_context", "readback"
    } or (ruleset["id"] != RULESET_ID or ruleset["name"] != "codeQA-main-protection"
          or ruleset["required_check_context"] != REQUIRED_CONTEXT
          or ruleset["readback"] != "GITHUB_RULESET_READBACK_VERIFIED_AT_OBSERVED_DATE_NOT_LIVE_CI_PROOF"):
        raise WorkflowCatalogError("unverified or invented branch ruleset authority")
    entries = manifest["workflows"]
    if not isinstance(entries, list) or not entries:
        raise WorkflowCatalogError("empty workflow inventory")
    actual = sorted(p for p in tracked_paths if p.startswith(".github/workflows/") and p.endswith((".yml", ".yaml")))
    recorded = []
    required = []
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != ENTRY_KEYS:
            raise WorkflowCatalogError("invalid workflow catalog entry")
        path, category = entry["path"], entry["category"]
        if (not isinstance(path, str) or not re.fullmatch(r"\.github/workflows/[a-z0-9-]+\.ya?ml", path)
                or category not in CATEGORIES or path not in workflow_sources):
            raise WorkflowCatalogError("unknown workflow path or category")
        recorded.append(path)
        if entry["artifact_authority"] != AUTHORITY[category]:
            raise WorkflowCatalogError("artifact authority escalation")
        if entry["owner"] != (
            "Samuel target-owned operations" if category == "operations"
            else "codeQA source/conformance"
        ):
            raise WorkflowCatalogError("incorrect workflow owner")
        if entry["retention_status"] != "WORKFLOW_DEFAULT_OR_POLICY_NOT_INDEPENDENTLY_EVALUATED":
            raise WorkflowCatalogError("invented artifact retention guarantee")
        text = workflow_sources[path]
        if not isinstance(text, str) or _events(text) != entry["trigger_events"]:
            raise WorkflowCatalogError("workflow triggers differ from manifest")
        observed_uploads = len(re.findall(r"uses:\s*actions/upload-artifact@", text))
        if type(entry["artifact_upload_count"]) is not int or entry["artifact_upload_count"] != observed_uploads:
            raise WorkflowCatalogError("workflow artifact upload count drift")
        if category == "required":
            required.append(path)
            if (entry["required_check"] != REQUIRED_CONTEXT
                    or entry["required_status"] != "OBSERVED_REQUIRED_BY_RULESET_25360323"
                    or not re.search(r"(?m)^\s{4}name:\s*layout\s*$", text)):
                raise WorkflowCatalogError("required check must be evidenced by ruleset and job name")
        elif (entry["required_check"] is not None
              or entry["required_status"] != "NOT_REQUIRED_BY_OBSERVED_RULESET"):
            raise WorkflowCatalogError("non-required workflow claims required check")
    if sorted(recorded) != actual or len(set(recorded)) != len(recorded):
        raise WorkflowCatalogError("unclassified, stale or duplicate workflow paths")
    if required != [".github/workflows/layout.yml"]:
        raise WorkflowCatalogError("required workflow set does not match observed ruleset")


def audit_workflow_catalog(root: Path) -> None:
    import json
    from codeqa.infrastructure.git import GitReader

    root = Path(root)
    manifest = json.loads((root / "docs/workflow-catalog-v0.1.json").read_text())
    tracked = GitReader(root).tracked_paths()
    sources = {
        path: (root / path).read_text(encoding="utf-8")
        for path in tracked if path.startswith(".github/workflows/") and path.endswith((".yml", ".yaml"))
    }
    validate_workflow_catalog(manifest, tracked, sources)


if __name__ == "__main__":
    audit_workflow_catalog(Path(__file__).resolve().parents[3])
    print("workflow catalog source audit verified; live ruleset and retention NOT_EVALUATED")
