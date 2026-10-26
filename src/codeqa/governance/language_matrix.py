"""Evidence-bounded language/layer support inventory (#122), never QA PASS."""
from __future__ import annotations

import ast
from collections.abc import Mapping
from pathlib import Path
import re
from typing import Any


class LanguageMatrixError(ValueError):
    """A language capability cell lacks the claimed scope/evidence."""


LAYERS = {"parser", "ccg", "mechanical_p1p3", "naming", "formal_gate", "production_abi"}
LANGUAGES = {"Python", "Rust", "C++/MOOSE", "Dafny-generated Python"}
STATUSES = {"SUPPORTED_SCOPED", "PARTIAL_FIXTURE", "FIXTURE_ONLY", "NOT_EVALUATED"}
CELL_KEYS = {"layer", "status", "source", "entrypoint", "workflow", "limitation"}
# The Python v0.1 scopes are syntax witnesses; changing prose cannot
# silently turn unresolved runtime calls into independently attested dispatch.
PYTHON_SCOPE_LIMITS = {
    "parser": "caller-supplied Python AST syntax only",
    "ccg": "CCG v0.1 source facts, unresolved runtime calls",
    "mechanical_p1p3": "heuristic P1/P3 only, no P1-P8 certificate",
}


def _path(root: Path, name: str) -> Path:
    if (not isinstance(name, str) or not name
            or name.startswith("/") or "\\" in name or ":" in name
            or any(ord(char) < 32 or ord(char) == 127 for char in name)
            or any(part in ("", ".", "..") or part.endswith((".", " "))
                   for part in name.split("/"))):
        raise LanguageMatrixError("invalid evidence path")
    base = root.resolve()
    candidate = (base / name).resolve()
    if not candidate.is_relative_to(base) or not candidate.is_file():
        raise LanguageMatrixError("missing or escaped evidence path: " + name)
    return candidate


def validate_language_matrix(root: Path, manifest: Mapping[str, Any]) -> None:
    if not isinstance(manifest, Mapping) or set(manifest) != {
        "schema_version", "baseline_source_sha", "evidence_level", "languages"
    } or manifest["schema_version"] != "0.1" or (
        manifest["evidence_level"] != "SOURCE_AND_WORKFLOW_DECLARATION_ONLY_NO_IMPLICIT_CI_PASS"
    ) or not re.fullmatch(r"[0-9a-f]{40}", manifest["baseline_source_sha"]):
        raise LanguageMatrixError("unversioned or untrusted capability manifest")
    entries = manifest["languages"]
    if not isinstance(entries, list) or len(entries) != len(LANGUAGES):
        raise LanguageMatrixError("incomplete language inventory")
    seen = set()
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {"language", "layers"}:
            raise LanguageMatrixError("invalid language row")
        lang = entry["language"]
        if lang not in LANGUAGES or lang in seen:
            raise LanguageMatrixError("unknown/duplicate language")
        seen.add(lang)
        cells = entry["layers"]
        if not isinstance(cells, list) or len(cells) != len(LAYERS):
            raise LanguageMatrixError("incomplete layer inventory")
        layer_ids = set()
        for cell in cells:
            if not isinstance(cell, dict) or set(cell) != CELL_KEYS:
                raise LanguageMatrixError("invalid capability cell")
            layer, status = cell["layer"], cell["status"]
            if layer not in LAYERS or layer in layer_ids or status not in STATUSES:
                raise LanguageMatrixError("duplicate/unknown layer or status")
            layer_ids.add(layer)
            if not isinstance(cell["limitation"], str) or len(cell["limitation"]) < 15:
                raise LanguageMatrixError("missing bounded limitation")
            if (status == "SUPPORTED_SCOPED"
                    and (lang != "Python" or layer not in {"parser", "ccg", "mechanical_p1p3"})):
                raise LanguageMatrixError("unsupported language/layer promoted to full support")
            if lang == "Python" and layer in PYTHON_SCOPE_LIMITS:
                if status != "SUPPORTED_SCOPED" or cell["limitation"] != PYTHON_SCOPE_LIMITS[layer]:
                    raise LanguageMatrixError("Python syntax-only support boundary changed")
            if layer == "production_abi" and status != "NOT_EVALUATED":
                raise LanguageMatrixError("production SDK/ABI compatibility not attested")
            if lang != "Python" and layer == "mechanical_p1p3" and status != "NOT_EVALUATED":
                if status != "PARTIAL_FIXTURE" or lang != "C++/MOOSE":
                    raise LanguageMatrixError("non-Python Mechanical parity falsely claimed")
            if status == "NOT_EVALUATED":
                if any(cell[key] is not None for key in ("source", "entrypoint", "workflow")):
                    raise LanguageMatrixError("not-evaluated cell cannot imply executed support")
                continue
            if cell["source"] is not None:
                _path(root, cell["source"])
            if cell["workflow"] is not None:
                _path(root, cell["workflow"])
            if status == "SUPPORTED_SCOPED" and (not cell["source"] or not cell["workflow"]):
                raise LanguageMatrixError("SUPPORTED requires source and CI workflow witnesses")
            if cell["entrypoint"] is not None:
                module, sep, symbol = cell["entrypoint"].partition(":")
                if (sep != ":" or not re.fullmatch(r"codeqa(?:\.[a-z_][a-z0-9_]*)+", module)
                        or cell["source"] != "src/" + module.replace(".", "/") + ".py"):
                    raise LanguageMatrixError("invalid language entrypoint source")
                tree = ast.parse(_path(root, cell["source"]).read_text())
                if symbol not in {
                    node.name for node in tree.body
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
                }:
                    raise LanguageMatrixError("missing language entrypoint")
            elif status == "SUPPORTED_SCOPED":
                raise LanguageMatrixError("SUPPORTED requires a real callable entrypoint")
            if status == "FIXTURE_ONLY" and (
                layer != "formal_gate" or lang not in {"Python", "Dafny-generated Python"}
            ):
                raise LanguageMatrixError("fixture authority promoted to other language/layer")
    if seen != LANGUAGES:
        raise LanguageMatrixError("language inventory missing rows")


def audit_language_matrix(root: Path) -> None:
    import json
    validate_language_matrix(
        root, json.loads((Path(root) / "profiles/language-execution-matrix-v0.1.json").read_text())
    )


if __name__ == "__main__":
    audit_language_matrix(Path(__file__).resolve().parents[3])
    print("language execution matrix: source declarations verified, runtime parity NOT_EVALUATED")
