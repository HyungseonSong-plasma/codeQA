#!/usr/bin/env python3
"""Compare codeQA before/after snapshots under ONE analyzer and ONE profile.

Measured syntax/graph observations are evidence, not proof of cohesion, SRP,
or behavioral equivalence. No inspected source code is executed.
"""
from __future__ import annotations

import argparse
import ast
from collections import Counter
import json
import math
from pathlib import Path
from statistics import mean, median

from codeqa.infrastructure.git import GitReader


ROOT = Path(__file__).resolve().parents[2]
FOCUS = (
    "src/codeqa/core/validation.py::validate_semantics",
    "src/codeqa/evaluation/mechanical.py::evaluate_mechanical",
    "src/codeqa/adapters/python.py::adapt_python_sources",
    "src/codeqa/core/graph.py::Graph.from_document",
    "src/codeqa/evaluation/layout.py::evaluate_layout",
    "src/codeqa/core/validation.py::parse_graph",
)


def _function_key(node_id: str) -> str:
    if not node_id.startswith("def::"):
        raise ValueError("unexpected function node ID: " + node_id)
    source, qualified = node_id[5:].split("::", 1)
    return source + "::" + qualified.rsplit("@", 1)[0]


def _metrics(analysis: dict) -> dict[str, dict]:
    return {
        _function_key(metric["node_id"]): metric
        for metric in analysis["scopes"]["production"]["quality"]["call_metrics"]
    }


def _distribution(values: list[int]) -> dict:
    if not values:
        return {"count": 0, "mean": None, "median": None, "p90": None, "max": None}
    sorted_values = sorted(values)
    return {
        "count": len(values),
        "mean": round(mean(values), 2),
        "median": median(values),
        "p90": sorted_values[math.ceil(0.9 * len(values)) - 1],
        "max": max(values),
    }


class _BranchCounter(ast.NodeVisitor):
    """A consistently-defined branch proxy, not McCabe or cognitive complexity."""

    def __init__(self) -> None:
        self.points = 0

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        pass  # nested function belongs to its own scope

    visit_AsyncFunctionDef = visit_FunctionDef
    visit_ClassDef = visit_FunctionDef
    visit_Lambda = visit_FunctionDef

    def generic_visit(self, node: ast.AST) -> None:
        if isinstance(node, (
            ast.If, ast.IfExp, ast.For, ast.AsyncFor, ast.While,
            ast.ExceptHandler,
        )):
            self.points += 1
        elif isinstance(node, ast.BoolOp):
            self.points += len(node.values) - 1
        elif isinstance(node, ast.Match):
            self.points += max(0, len(node.cases) - 1)
        elif isinstance(node, ast.comprehension):
            self.points += len(node.ifs) + 1
        super().generic_visit(node)


class _Functions(ast.NodeVisitor):
    def __init__(self, path: str) -> None:
        self.path = path
        self.names: list[str] = []
        self.branches: dict[str, int] = {}

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.names.append(node.name)
        for stmt in node.body:
            self.visit(stmt)
        self.names.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        qualified = ".".join([*self.names, node.name])
        counter = _BranchCounter()
        for stmt in node.body:
            counter.visit(stmt)
        key = self.path + "::" + qualified
        # Multiple defs of the same qualified name are ambiguous; retain
        # the worst-case branch count, not an arbitrary last definition.
        self.branches[key] = max(self.branches.get(key, 0), 1 + counter.points)
        self.names.append(node.name)
        for stmt in node.body:
            self.visit(stmt)
        self.names.pop()

    visit_AsyncFunctionDef = visit_FunctionDef


def _module_name(path: str) -> str:
    name = path.removeprefix("src/").removesuffix(".py").replace("/", ".")
    return name.removesuffix(".__init__")


def _dependency_edges(trees: dict[str, ast.Module]) -> set[tuple[str, str]]:
    """Conservative syntactic, intra-codeQA import edges; no dynamic imports."""
    modules = {_module_name(path) for path in trees}
    edges: set[tuple[str, str]] = set()

    def match_module(candidate: str) -> str | None:
        while candidate:
            if candidate in modules:
                return candidate
            candidate = candidate.rpartition(".")[0]
        return None

    for path, tree in trees.items():
        origin = _module_name(path)
        package = origin if path.endswith("/__init__.py") else origin.rpartition(".")[0]
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                candidates = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    parts = package.split(".")
                    remain = len(parts) - (node.level - 1)
                    prefix = ".".join(parts[:remain]) if remain > 0 else ""
                    candidates = [prefix + ("." + node.module if node.module else "")]
                else:
                    candidates = [node.module or ""]
            else:
                continue
            for name in candidates:
                if not name.startswith("codeqa"):
                    continue
                target = match_module(name)
                if target and target != origin:
                    edges.add((origin, target))
    return edges


def _source_structure(reader: GitReader, analysis: dict) -> dict:
    sha = analysis["snapshot_sha"]
    paths = analysis["scopes"]["production"]["source_paths"]
    trees = {
        path: ast.parse(reader.read_file(sha, path).decode("utf-8"), filename=path)
        for path in paths
    }
    functions: dict[str, int] = {}
    for path, tree in trees.items():
        collector = _Functions(path)
        collector.visit(tree)
        functions.update(collector.branches)
    imports = _dependency_edges(trees)
    cross_package = sorted([
        [source, target]
        for source, target in imports
        if source.split(".")[1] != target.split(".")[1]
    ])
    branch_points_by_module = {
        path: sum(
            score - 1
            for key, score in functions.items()
            if key.startswith(path + "::")
        )
        for path in sorted(trees)
    }
    return {
        "branch_points_by_module": branch_points_by_module,
        "branch_proxy": functions,
        "import_module_pairs": len(imports),
        "cross_package_import_pairs": len(cross_package),
        "cross_package_imports": cross_package,
        "branch_distribution": _distribution(list(functions.values())),
    }


def compare(before: dict, after: dict, reader: GitReader) -> dict:
    if before["snapshot_sha"] == after["snapshot_sha"]:
        raise ValueError("comparison requires distinct source revisions")
    if before["analyzer_sha"] != after["analyzer_sha"]:
        raise ValueError("both snapshots MUST be evaluated by the same analyzer")
    if before["profile"] != after["profile"]:
        raise ValueError("profiles differ: no comparable verdicts")
    b, a = _metrics(before), _metrics(after)
    structural_before = _source_structure(reader, before)
    structural_after = _source_structure(reader, after)

    def snapshot(analysis: dict, metrics: dict, structural: dict) -> dict:
        q = analysis["scopes"]["production"]["quality"]
        sites = [m["call_sites"] for m in metrics.values()]
        distinct = [m["distinct_resolved_targets"] for m in metrics.values()]
        return {
            "sha": analysis["snapshot_sha"],
            "files": analysis["scopes"]["production"]["source_files"],
            "functions": q["function_count"],
            "findings": len(q["findings"]),
            "status": q["status"],
            "analysis_status": q["analysis_status"],
            "unresolved_edges": q["unresolved_edges"],
            "total_call_sites": sum(sites),
            "call_sites_per_function": _distribution(sites),
            "distinct_resolved_targets_per_function": _distribution(distinct),
            "functions_over_call_threshold": sum(
                v > analysis["profile"]["max_call_sites"] for v in sites
            ),
            "syntax_branch_proxy": structural["branch_distribution"],
            "total_ast_branch_points": sum(structural["branch_points_by_module"].values()),
            "branch_points_by_module": structural["branch_points_by_module"],
            "unique_import_module_pairs": structural["import_module_pairs"],
            "cross_package_import_pairs": structural["cross_package_import_pairs"],
            "cross_package_imports": structural["cross_package_imports"],
        }

    focus = {}
    for key in FOCUS:
        old = b.get(key)
        new = a.get(key)
        focus[key] = {
            "before_calls": old["call_sites"] if old else None,
            "after_calls": new["call_sites"] if new else None,
            "before_targets": old["distinct_resolved_targets"] if old else None,
            "after_targets": new["distinct_resolved_targets"] if new else None,
            "before_branch_proxy": structural_before["branch_proxy"].get(key),
            "after_branch_proxy": structural_after["branch_proxy"].get(key),
        }

    shared = set(b) & set(a)
    changes = sorted(
        (
            {
                "name": key,
                "before_calls": b[key]["call_sites"],
                "after_calls": a[key]["call_sites"],
                "before_branch_proxy": structural_before["branch_proxy"].get(key),
                "after_branch_proxy": structural_after["branch_proxy"].get(key),
            }
            for key in shared
        ),
        key=lambda record: (
            (record["after_calls"] - record["before_calls"]),
            record["name"],
        ),
    )
    return {
        "analyzer_sha": before["analyzer_sha"],
        "profile": before["profile"],
        "before": snapshot(before, b, structural_before),
        "after": snapshot(after, a, structural_after),
        "same_named_functions": len(shared),
        "removed_functions": sorted(set(b) - set(a)),
        "added_functions": sorted(set(a) - set(b)),
        "focus": focus,
        "largest_call_count_decreases": changes[:8],
        "largest_call_count_increases": list(reversed(changes[-8:])),
        "interpretation": (
            "Call sites, known targets, and AST branch proxies are separate "
            "observations. Branch proxy is not validated cyclomatic complexity; "
            "cross-package imports are syntax-observed only. Increased function "
            "count can distort averages. No measure here proves SRP, cohesion "
            "or reduction of runtime coupling."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before", type=Path, required=True)
    parser.add_argument("--after", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    before = json.loads(args.before.read_text(encoding="utf-8"))
    after = json.loads(args.after.read_text(encoding="utf-8"))
    result = compare(before, after, GitReader(ROOT))
    args.output.write_text(
        json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print("COMPARISON analyzer_sha=" + result["analyzer_sha"])
    for key in ("before", "after"):
        s = result[key]
        print(
            f"COMPARISON {key}: files={s['files']} functions={s['functions']} "
            f"findings={s['findings']} total_calls={s['total_call_sites']} "
            f"max_calls={s['call_sites_per_function']['max']} "
            f"p90_calls={s['call_sites_per_function']['p90']} "
            f"max_branch_proxy={s['syntax_branch_proxy']['max']} "
            f"total_branch_points={s['total_ast_branch_points']} "
            f"cross_package_import_pairs={s['cross_package_import_pairs']}"
        )
    for path in (
        "src/codeqa/core/validation.py",
        "src/codeqa/evaluation/mechanical.py",
        "src/codeqa/adapters/python.py",
    ):
        bpoints = result["before"]["branch_points_by_module"].get(path)
        apoints = result["after"]["branch_points_by_module"].get(path)
        print(f"MODULE_BRANCH {path}: {bpoints}->{apoints}")
    for name, record in result["focus"].items():
        print(
            f"FOCUS {name}: calls={record['before_calls']}->{record['after_calls']} "
            f"targets={record['before_targets']}->{record['after_targets']} "
            f"branch={record['before_branch_proxy']}->{record['after_branch_proxy']}"
        )
    print(
        f"COMPARISON shared_functions={result['same_named_functions']} "
        f"added={len(result['added_functions'])} "
        f"removed={len(result['removed_functions'])}"
    )
    print("COMPARISON artifact: " + str(args.output))


if __name__ == "__main__":
    main()
