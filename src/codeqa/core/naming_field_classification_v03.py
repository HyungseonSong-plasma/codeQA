"""Bounded source-only Python dataclass field evidence for Naming #91.

This optional classifier cannot certify runtime fields, human policy decisions,
semantic naming correctness, or rename safety. It never imports target source.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass
from hashlib import sha256
import re


class FieldClassificationError(ValueError):
    """Invalid source identity or missing/nonunique direct annotated site."""


@dataclass(frozen=True, slots=True)
class FieldClassification:
    name: str
    owner: str
    line: int
    ast_node: str
    annotation_site: str
    classification: str
    reasons: tuple[str, ...]
    runtime_field_verification: str = "NOT_EVALUATED"
    naming_policy_applicability: str = "NOT_EVALUATED"
    rename_authorized: bool = False


_BUILTINS = frozenset({"str", "int", "float", "bool", "bytes", "object",
                       "tuple", "list", "dict", "set", "frozenset", "complex"})
_SPECIAL = {"typing.ClassVar": "CLASSVAR_PSEUDO_FIELD",
            "typing_extensions.ClassVar": "CLASSVAR_PSEUDO_FIELD",
            "dataclasses.InitVar": "INITVAR_PSEUDO_FIELD",
            "dataclasses.KW_ONLY": "KW_ONLY_PSEUDO_FIELD"}
_RESERVED = frozenset({"ClassVar", "InitVar", "KW_ONLY", "Final"})
_DATACLASS_FLAGS = frozenset({"init", "repr", "eq", "order", "unsafe_hash",
                               "frozen", "match_args", "kw_only", "slots", "weakref_slot"})


def _bound(target: ast.AST) -> set[str]:
    if isinstance(target, ast.Name):
        return {target.id}
    if isinstance(target, (ast.Tuple, ast.List)):
        return set().union(*(_bound(x) for x in target.elts))
    return set()


def _module_bindings(statements: list[ast.stmt]) -> dict[str, tuple[str, ...]]:
    names: dict[str, list[str]] = {}

    def add(name: str, origin: str) -> None:
        names.setdefault(name, []).append(origin)

    for stmt in statements:
        if isinstance(stmt, ast.ImportFrom):
            for item in stmt.names:
                if item.name == "*":
                    add("*", "WILDCARD_IMPORT")
                else:
                    add(item.asname or item.name,
                        "." * stmt.level + (stmt.module or "") + "." + item.name)
        elif isinstance(stmt, ast.Import):
            for item in stmt.names:
                add(item.asname or item.name.split(".")[0], item.name)
        elif isinstance(stmt, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            targets = stmt.targets if isinstance(stmt, ast.Assign) else [stmt.target]
            for name in set().union(*(_bound(t) for t in targets)):
                add(name, "REBOUND")
        elif isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            add(stmt.name, "LOCAL_DEFINITION")
        elif isinstance(stmt, (ast.If, ast.With, ast.For, ast.While, ast.Try,
                               ast.AsyncFor, ast.AsyncWith)):
            add("*", "DYNAMIC_MODULE_BINDING")
        elif isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
            add("*", "UNKNOWN_MODULE_SIDE_EFFECT")
    return {name: tuple(values) for name, values in names.items()}


def _origin(expr: ast.AST, names: dict[str, tuple[str, ...]]) -> str | None:
    if isinstance(expr, ast.Name):
        origins = names.get(expr.id, ())
        return origins[0] if len(origins) == 1 and "*" not in names else None
    if isinstance(expr, ast.Attribute):
        base = _origin(expr.value, names)
        return base + "." + expr.attr if base is not None else None
    return None


def _stdlib_dataclass(cls: ast.ClassDef,
                      names: dict[str, tuple[str, ...]]) -> bool:
    if len(cls.decorator_list) != 1:
        return False
    expr = cls.decorator_list[0]
    if isinstance(expr, ast.Call):
        if expr.args or any(k.arg not in _DATACLASS_FLAGS or
                            not isinstance(k.value, ast.Constant) or
                            type(k.value.value) is not bool for k in expr.keywords):
            return False
        expr = expr.func
    return _origin(expr, names) == "dataclasses.dataclass"


def _annotation(annotation: ast.AST,
                names: dict[str, tuple[str, ...]]) -> tuple[str, str]:
    root = annotation.value if isinstance(annotation, ast.Subscript) else annotation
    if isinstance(root, (ast.Name, ast.Attribute)):
        origin = _origin(root, names)
        if origin in _SPECIAL:
            return "PSEUDO_FIELD_EXCLUDED", _SPECIAL[origin]
        if origin in {"typing.Final", "typing_extensions.Final"}:
            return "REVIEW_REQUIRED", "FINAL_IS_NOT_A_PSEUDO_FIELD"
        if isinstance(root, ast.Name):
            if root.id in _RESERVED:
                return "REVIEW_REQUIRED", "SPECIAL_ANNOTATION_BINDING_UNRESOLVED"
            if root.id in _BUILTINS and root.id not in names and "*" not in names:
                return "FIELD_CANDIDATE", "STATIC_STDLIB_DATACLASS_ANNOTATION"
    return "REVIEW_REQUIRED", "ANNOTATION_TYPE_OR_ALIAS_UNRESOLVED"


def classify_pinned_class_annotation(
    source: bytes, *, expected_sha256: str,
    owner: str, name: str, line: int,
) -> FieldClassification:
    """Classify one exact, direct top-level class annotation without execution.

    FIELD_CANDIDATE is not FIELD_CONFIRMED and is not rename eligibility.
    """
    if (not isinstance(source, bytes) or not isinstance(expected_sha256, str)
            or not re.fullmatch(r"[0-9a-f]{64}", expected_sha256)
            or sha256(source).hexdigest() != expected_sha256
            or not isinstance(owner, str) or not owner.isidentifier()
            or not isinstance(name, str) or not name.isidentifier()
            or type(line) is not int or line < 1):
        raise FieldClassificationError("exact source digest and target identity required")
    try:
        tree = ast.parse(source.decode("utf-8"))
    except (SyntaxError, UnicodeDecodeError) as exc:
        raise FieldClassificationError("source not parseable UTF-8 Python") from exc
    classes = [s for s in tree.body if isinstance(s, ast.ClassDef) and s.name == owner]
    if len(classes) != 1:
        raise FieldClassificationError("unique top-level class owner required")
    cls = classes[0]
    sites = [s for s in cls.body if isinstance(s, ast.AnnAssign)
             and isinstance(s.target, ast.Name)
             and s.target.id == name and s.lineno == line]
    if len(sites) != 1:
        raise FieldClassificationError("exact direct AnnAssign name/line required")
    site = sites[0]

    def result(kind: str, reason: str) -> FieldClassification:
        return FieldClassification(name, owner, line, "AnnAssign",
                                   "DIRECT_CLASS_ANNASSIGN", kind, (reason,))

    if site.simple != 1:
        return result("REVIEW_REQUIRED", "PARENTHESIZED_NAME_NOT_SIMPLE")

    all_names = _module_bindings(tree.body)
    index = next(i for i, stmt in enumerate(tree.body) if stmt is cls)
    before_names = _module_bindings(tree.body[:index])
    if cls.bases or cls.keywords:
        return result("REVIEW_REQUIRED", "INHERITANCE_OR_METACLASS")
    if not _stdlib_dataclass(cls, all_names) or not _stdlib_dataclass(cls, before_names):
        return result("REVIEW_REQUIRED", "DECORATOR_IDENTITY_OR_COMPOSITION_UNKNOWN") if cls.decorator_list else (
            result("CLASS_ANNOTATION_ONLY", "NOT_A_STDLIB_DATACLASS_DECLARATION"))

    annotation_root = site.annotation.value if isinstance(site.annotation, ast.Subscript) else site.annotation
    for sibling in cls.body:
        if sibling is site or isinstance(sibling, ast.Pass):
            continue
        if isinstance(sibling, ast.Expr) and isinstance(sibling.value, ast.Constant):
            continue
        if isinstance(sibling, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            targets = sibling.targets if isinstance(sibling, ast.Assign) else [sibling.target]
            bindings = set().union(*(_bound(t) for t in targets))
            if name in bindings or "__annotations__" in bindings:
                return result("REVIEW_REQUIRED", "FIELD_REBOUND_OR_ANNOTATIONS_CHANGED")
            if isinstance(annotation_root, ast.Name) and annotation_root.id in bindings:
                return result("REVIEW_REQUIRED", "ANNOTATION_SYMBOL_SHADOWED_IN_CLASS")
        elif isinstance(sibling, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if sibling.name == name:
                return result("REVIEW_REQUIRED", "FIELD_REDEFINED")
            if isinstance(annotation_root, ast.Name) and sibling.name == annotation_root.id:
                return result("REVIEW_REQUIRED", "ANNOTATION_SYMBOL_SHADOWED_IN_CLASS")
        else:
            return result("REVIEW_REQUIRED", "UNMODELED_CLASS_BODY_MUTATION")
    if site.value is not None and not isinstance(site.value, ast.Constant):
        return result("REVIEW_REQUIRED", "DYNAMIC_DEFAULT_FACTORY_OR_DESCRIPTOR")
    kind, reason = _annotation(site.annotation, all_names)
    return result(kind, reason)
