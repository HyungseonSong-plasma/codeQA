"""Read-only, fail-closed audit of codeQA's declared consumer support surface.

This checks source symbols, registered resource coverage and README projection,
NOT runtime correctness, human usability or whether any external CI ran.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path
import re
import tomllib
from typing import Any, Mapping


class SupportSurfaceError(ValueError):
    """The support inventory makes an unverifiable or contradictory claim."""


START = "<!-- support-surface:v0.1:start -->"
END = "<!-- support-surface:v0.1:end -->"
MODES = {"DEFAULT_SCOPED", "OPT_IN", "CONTRACT_ONLY", "FIXTURE_ONLY", "NOT_IMPLEMENTED"}
AUTHORITY = {
    "DEFAULT_SCOPED": {"HEURISTIC_REVIEW"},
    "OPT_IN": {"SCOPED_REVIEW", "SCOPED_GATE"},
    "CONTRACT_ONLY": {"CONTRACT_ONLY"},
    "FIXTURE_ONLY": {"FIXTURE_ONLY"},
    "NOT_IMPLEMENTED": {"NONE"},
}
KEYS = {
    "id", "mode", "languages", "authority", "scope", "source",
    "entrypoint", "evidence", "resources", "principles", "limitations",
}
REQUIRED = {
    "python_mechanical", "mechanical_p2_p4_p8",
    "non_python_mechanical", "formal_generated_fixture",
}

# Protected public meanings cannot change through an internally consistent
# README/manifest edit without a separately reviewed versioned contract.
PROTECTED_BOUNDARIES = {
    "python_naming_safe": ("OPT_IN", "SCOPED_REVIEW", "PYTHON_DECLARATION_SPELLING_ONLY"),
    "naming_companions": ("OPT_IN", "SCOPED_REVIEW", "EXPERIMENTAL_DECLARATION_WITNESSES"),
    "official_naming_v05_exact_field": ("OPT_IN", "SCOPED_REVIEW", "EXACT_FIELD_LEXICAL_ONLY"),
    "external_evidence_gate": ("OPT_IN", "SCOPED_GATE", "PINNED_ADMITTED_EXTERNAL_EVIDENCE_ONLY"),
    "qa_result_contract": ("CONTRACT_ONLY", "CONTRACT_ONLY", "SCOPED_MECHANICAL_EXCHANGE_ONLY"),
    "formal_generated_fixture": ("FIXTURE_ONLY", "FIXTURE_ONLY", "CONTROLLED_GENERATED_PYTHON_FIXTURE"),
}


# A coherent README edit cannot manufacture a second default pipeline, a new
# policy Gate, or an additional Formal fixture authority. Such expansion needs
# a separately reviewed, versioned supported-surface contract.
EXCLUSIVE_MODES = {
    "DEFAULT_SCOPED": {"python_mechanical"},
    "FIXTURE_ONLY": {"formal_generated_fixture"},
}
EXCLUSIVE_AUTHORITIES = {"SCOPED_GATE": {"external_evidence_gate"}}
PROTECTED_SOURCE_IDENTITIES = {
    "python_mechanical": (("Python",), "codeqa.pipeline.python:analyze_python"),
    "python_naming_safe": (("Python",), "codeqa.evaluation.naming:evaluate_naming"),
    "naming_companions": (("Python",), "codeqa.evaluation.naming:evaluate_naming"),
    "official_naming_v05_exact_field": (("Python",), "codeqa.pipeline.naming_official_policy_v05:evaluate_pinned_official_naming_v05"),
    "external_evidence_gate": (("language-neutral",), "codeqa.evaluation.evidence_gate:evaluate_gate"),
    "formal_generated_fixture": (("Dafny", "Python"), "codeqa.evaluation.formal_generated_gate:evaluate_generated_fixture_gate"),
    "qa_result_contract": (("language-neutral", "Python"), "codeqa.evaluation.qa_result:validate_qa_result"),
}


def _reject(message: str) -> None:
    raise SupportSurfaceError(message)


def _path(root: Path, value: str) -> Path:
    if (not isinstance(value, str) or not value or value.startswith("/")
            or "\\" in value or ":" in value
            or any(ord(char) < 32 or ord(char) == 127 for char in value)
            or any(x in ("", ".", "..") or x.endswith((".", " "))
                   for x in value.split("/"))
            or (len(value) > 1 and value[1] == ":")):
        _reject("unsafe or empty support path")
    base = root.resolve()
    candidate = (base / value).resolve()
    if not candidate.is_relative_to(base) or not candidate.is_file():
        _reject("missing or escaped support path: " + value)
    return candidate


def render_support_table(manifest: Mapping[str, Any]) -> str:
    """A single deterministic consumer table, without guessed PASS claims."""
    rows = [
        "| Feature | Mode | Language | Authority | Evidence scope |",
        "| --- | --- | --- | --- | --- |",
    ]
    for feature in manifest["features"]:
        values = (
            feature["id"], feature["mode"], ", ".join(feature["languages"]),
            feature["authority"], feature["scope"],
        )
        if any(not isinstance(x, str) or not x or "|" in x
               or any(ord(char) < 32 or ord(char) == 127 for char in x)
               for x in values):
            _reject("unsafe README table cell")
        rows.append("| " + " | ".join(values) + " |")
    return "\n".join(rows)


def audit_support_surface(
    root: Path, manifest: Mapping[str, Any], *, readme: str | None = None,
) -> None:
    """Validate claims against this checkout, without importing inspected code."""
    root = Path(root)
    if not isinstance(manifest, Mapping) or set(manifest) != {
        "schema_version", "package", "release", "evidence_level", "features"
    }:
        _reject("unexpected support manifest fields")
    if manifest["schema_version"] != "0.1" or manifest["evidence_level"] != "SOURCE_WITNESS_ONLY":
        _reject("unsupported manifest or evidence level")
    with (root / "pyproject.toml").open("rb") as handle:
        project = tomllib.load(handle)
    if (manifest["package"] != project.get("project", {}).get("name")
            or manifest["release"] != project.get("project", {}).get("version")
            or project.get("project", {}).get("readme") != "README.md"):
        _reject("package metadata and support manifest disagree")
    registry = project.get("tool", {}).get("codeqa", {}).get("resources")
    if not isinstance(registry, dict) or not registry:
        _reject("missing registered resources")
    for rid, path in registry.items():
        if not isinstance(rid, str) or not re.fullmatch(r"[a-z][a-z0-9_]*", rid):
            _reject("invalid registered resource ID")
        _path(root, path)
    features = manifest["features"]
    if not isinstance(features, list) or not features:
        _reject("missing feature inventory")
    ids: set[str] = set()
    assigned: list[str] = []
    for feature in features:
        if not isinstance(feature, dict) or set(feature) != KEYS:
            _reject("invalid feature fields")
        fid = feature["id"]
        if not isinstance(fid, str) or not re.fullmatch(r"[a-z][a-z0-9_]*", fid) or fid in ids:
            _reject("duplicate or unsafe feature ID")
        ids.add(fid)
        mode, authority = feature["mode"], feature["authority"]
        if mode not in MODES or authority not in AUTHORITY[mode]:
            _reject("unsupported mode or authority escalation: " + fid)
        for field in ("languages", "evidence", "resources", "principles", "limitations"):
            values = feature[field]
            if not isinstance(values, list) or (field in ("languages", "evidence", "limitations") and not values):
                _reject("missing support field: " + fid + "." + field)
            if any(not isinstance(v, str) or not v or "|" in v
                   or any(ord(char) < 32 or ord(char) == 127 for char in v)
                   for v in values):
                _reject("invalid support field: " + fid + "." + field)
            if len(set(values)) != len(values):
                _reject("duplicate support field: " + fid + "." + field)
        if not isinstance(feature["scope"], str) or not re.fullmatch(r"[A-Z0-9_]+", feature["scope"]):
            _reject("invalid support scope")
        for path in feature["evidence"]:
            _path(root, path)
        for rid in feature["resources"]:
            if rid not in registry:
                _reject("invented registered resource: " + rid)
            assigned.append(rid)
        if mode == "NOT_IMPLEMENTED":
            if feature["source"] is not None or feature["entrypoint"] is not None or feature["resources"]:
                _reject("unsupported capability must not declare an implementation")
        else:
            source, entrypoint = feature["source"], feature["entrypoint"]
            if not isinstance(source, str) or not isinstance(entrypoint, str):
                _reject("implemented capability lacks a source symbol")
            module, sep, symbol = entrypoint.partition(":")
            if (sep != ":" or not re.fullmatch(r"codeqa(?:\.[a-z_][a-z0-9_]*)+", module)
                    or not re.fullmatch(r"[a-zA-Z_][a-zA-Z_0-9]*", symbol)
                    or source != "src/" + module.replace(".", "/") + ".py"):
                _reject("entrypoint and source mismatch: " + fid)
            parsed = ast.parse(_path(root, source).read_text(encoding="utf-8"))
            if symbol not in {
                node.name for node in parsed.body
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
            }:
                _reject("missing public source symbol: " + entrypoint)
        if (mode != "NOT_IMPLEMENTED"
                and any(p not in {"P1", "P3"} for p in feature["principles"])):
            _reject("unsupported Mechanical principle promoted: " + fid)
        if (mode != "NOT_IMPLEMENTED" and feature["principles"]
                and set(feature["languages"]) & {"Rust", "C++", "MOOSE"}):
            _reject("unverified non-Python Mechanical support")
    by_id = {f["id"]: f for f in features}
    if not set(PROTECTED_BOUNDARIES).issubset(ids):
        _reject("missing protected feature boundary")
    for fid, expected in PROTECTED_BOUNDARIES.items():
        feature = next(item for item in features if item["id"] == fid)
        if (feature["mode"], feature["authority"], feature["scope"]) != expected:
            _reject("protected feature activation/authority drift: " + fid)
    for mode, expected_ids in EXCLUSIVE_MODES.items():
        actual_ids = {f["id"] for f in features if f["mode"] == mode}
        if actual_ids != expected_ids:
            _reject("unreviewed exclusive support mode: " + mode)
    for authority, expected_ids in EXCLUSIVE_AUTHORITIES.items():
        actual_ids = {f["id"] for f in features if f["authority"] == authority}
        if actual_ids != expected_ids:
            _reject("unreviewed scoped authority: " + authority)
    for fid, (expected_languages, expected_entrypoint) in PROTECTED_SOURCE_IDENTITIES.items():
        feature = by_id[fid]
        if (tuple(feature["languages"]) != expected_languages
                or feature["entrypoint"] != expected_entrypoint):
            _reject("protected language/source identity drift: " + fid)
    # Source-level guard: the default Python Mechanical path must not import
    # opt-in Naming. Dynamic dispatch and runtime effects remain NOT_EVALUATED.
    default_source = _path(root, "src/codeqa/pipeline/python.py")
    default_ast = ast.parse(default_source.read_text(encoding="utf-8"))
    for node in ast.walk(default_ast):
        if isinstance(node, ast.Import):
            paths = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            paths = [node.module or ""]
            paths += [(node.module or "") + "." + alias.name for alias in node.names]
        else:
            continue
        if any(any(part.startswith("naming") or part == "python_naming"
                   for part in name.split(".")) for name in paths):
            _reject("default Python Mechanical module imports opt-in Naming")
    if ids < REQUIRED:
        _reject("mandatory negative capability not declared")
    mechanical = by_id["python_mechanical"]
    if (mechanical["mode"] != "DEFAULT_SCOPED"
            or mechanical["languages"] != ["Python"]
            or mechanical["principles"] != ["P1", "P3"]):
        _reject("Python default Mechanical scope drift")
    excluded = by_id["mechanical_p2_p4_p8"]
    if (excluded["mode"] != "NOT_IMPLEMENTED"
            or set(excluded["principles"]) != {"P2", "P4", "P5", "P6", "P7", "P8"}):
        _reject("unsupported P2/P4-P8 incorrectly represented")
    non_python = by_id["non_python_mechanical"]
    if (non_python["mode"] != "NOT_IMPLEMENTED"
            or set(non_python["languages"]) != {"Rust", "C++", "MOOSE"}):
        _reject("non-Python Mechanical parity not established")
    formal = by_id["formal_generated_fixture"]
    if (formal["mode"] != "FIXTURE_ONLY" or formal["authority"] != "FIXTURE_ONLY"
            or formal["scope"] != "CONTROLLED_GENERATED_PYTHON_FIXTURE"):
        _reject("fixture-only Formal authority promoted")
    if set(assigned) != set(registry) or len(assigned) != len(registry):
        _reject("registered resource inventory is incomplete or duplicated")
    if readme is None:
        readme = (root / "README.md").read_text(encoding="utf-8")
    if readme.count(START) != 1 or readme.count(END) != 1:
        _reject("missing or duplicated README support table markers")
    actual = readme.split(START, 1)[1].split(END, 1)[0].strip()
    if actual != render_support_table(manifest):
        _reject("README supported-surface table drift")


def audit_repository(root: Path) -> None:
    manifest = json.loads((root / "docs/support-surface-v0.1.json").read_text(encoding="utf-8"))
    audit_support_surface(root, manifest)


if __name__ == "__main__":
    audit_repository(Path(__file__).resolve().parents[3])
    print("support surface source inventory: verified (NOT a quality or CI PASS)")
