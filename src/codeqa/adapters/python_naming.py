"""Python source-only naming evidence; syntactic bindings are not runtime proof."""
from __future__ import annotations

import ast
from collections.abc import Mapping
from hashlib import sha256

from codeqa.core.naming import NamingEvidence, NamingSymbol
from .python_snapshot import ParsedSnapshot


def _dotted(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _dotted(node.value)
        return f"{parent}.{node.attr}" if parent else None
    return None


class _Declarations(ast.NodeVisitor):
    def __init__(self, path: str, tree: ast.Module) -> None:
        self.path = path
        self.tree = tree
        self.entries: list[NamingSymbol] = []
        self.imports: dict[str, str] = {}
        self.classes: dict[str, ast.ClassDef] = {}
        self.scope: list[str] = []
        for stmt in tree.body:
            if isinstance(stmt, ast.Import):
                for alias in stmt.names:
                    self.imports[alias.asname or alias.name.split(".")[0]] = alias.name
            if isinstance(stmt, ast.ImportFrom) and stmt.module:
                for alias in stmt.names:
                    if alias.name != "*":
                        self.imports[alias.asname or alias.name] = f"{stmt.module}.{alias.name}"
            if isinstance(stmt, ast.ClassDef):
                self.classes[stmt.name] = stmt

    def _add(self, node: ast.AST, name: str, kind: str, relation: str = "LOCAL",
             detail: str = "", contract_name: str | None = None) -> None:
        column = node.col_offset
        if isinstance(node, ast.AsyncFunctionDef):
            column += len("async def ")
        elif isinstance(node, ast.FunctionDef):
            column += len("def ")
        elif isinstance(node, ast.ClassDef):
            column += len("class ")
        elif isinstance(node, ast.alias) and node.asname == name:
            column = node.end_col_offset - len(name.encode("utf-8"))
        self.entries.append(NamingSymbol(
            self.path, ".".join(self.scope), name, kind,
            node.lineno, column, relation, contract_name, detail,
        ))

    def _override_intent(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
        for decorator in node.decorator_list:
            dotted = _dotted(decorator)
            if not dotted:
                continue
            parts = dotted.split(".")
            resolved = self.imports.get(parts[0], parts[0])
            qualified = ".".join([resolved, *parts[1:]])
            if qualified in ("typing.override", "typing_extensions.override"):
                return True
        return False

    def _ancestor(self, cls: ast.ClassDef, name: str,
                  seen: frozenset[str] = frozenset()) -> str:
        """A direct local class chain is sufficient for lexical-name matching.

        UNKNOWN if *any* branch cannot be resolved. Never decide that a
        parent lacks a member with an external ancestor or ambiguous bases.
        """
        if cls.name in seen:
            return "unknown"
        if cls.keywords or len(cls.bases) != 1:
            return "unknown" if cls.keywords or cls.bases else "absent"
        base = cls.bases[0]
        if not isinstance(base, ast.Name):
            return "unknown"
        parent = self.classes.get(base.id)
        if parent is None:
            return "unknown"
        for item in parent.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == name:
                return "matched"
        return self._ancestor(parent, name, seen | {cls.name})

    def _dto(self, cls: ast.ClassDef) -> bool:
        for base in cls.bases:
            dotted = _dotted(base)
            if dotted:
                root, *parts = dotted.split(".")
                q = ".".join([self.imports.get(root, root), *parts])
                if q in ("pydantic.BaseModel", "pydantic.main.BaseModel"):
                    return True
        return False

    def _field_alias(self, value: ast.AST | None) -> tuple[str, str | None]:
        if not isinstance(value, ast.Call):
            return "direct", None
        dotted = _dotted(value.func)
        if not dotted or dotted.split(".")[-1] not in ("Field", "mapped_column"):
            return "direct", None
        parts = dotted.split(".")
        resolved = ".".join([self.imports.get(parts[0], parts[0]), *parts[1:]])
        known = ("pydantic.Field", "pydantic.fields.Field",
                 "sqlalchemy.orm.mapped_column", "sqlalchemy.mapped_column")
        if resolved not in known:
            return "unknown", None
        aliases = {"alias", "validation_alias", "serialization_alias"}
        seen = [(k.arg, k.value) for k in value.keywords if k.arg in aliases]
        if dotted.split(".")[-1] == "mapped_column" and value.args:
            seen += [("database_column", value.args[0])]
        if not seen:
            return "unknown", None
        if any(not isinstance(v, ast.Constant) or
               not isinstance(v.value, str) for _, v in seen):
            return "unknown", None
        detail = ",".join(f"{key}={value.value}" for key, value in sorted(seen))
        return "literal", detail

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            if alias.asname:
                self._add(alias, alias.asname, "import_alias",
                          detail=f"external={alias.name}")
            else:
                self._add(alias, alias.name.split(".")[0], "import_alias",
                          relation="IMPORTED_ORIGINAL", detail=alias.name)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        for alias in node.names:
            if alias.name == "*":
                continue
            name = alias.asname or alias.name
            if alias.asname:
                self._add(alias, name, "import_alias",
                          detail=f"external={node.module}.{alias.name}")
            else:
                self._add(alias, name, "import_alias",
                          relation="IMPORTED_ORIGINAL",
                          detail=f"{node.module}.{alias.name}")

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._add(node, node.name, "class")
        self.scope.append(node.name)
        for stmt in node.body:
            self.visit(stmt)
        self.scope.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        cls = self.classes.get(self.scope[0]) if len(self.scope) == 1 else None
        relation, detail = "LOCAL", ""
        if cls is not None:
            ancestor = self._ancestor(cls, node.name)
            if ancestor == "matched":
                relation, detail = "LOCAL_OVERRIDE_MATCH", "local_class_ancestor_name"
            elif ancestor == "unknown":
                relation, detail = "EXTERNAL_BASE_UNRESOLVED", "ancestor_binding_not_proven"
            elif self._override_intent(node):
                relation, detail = "INVALID_OVERRIDE_INTENT", "no_local_ancestor_member"
            if self._override_intent(node) and relation == "EXTERNAL_BASE_UNRESOLVED":
                detail = "override_intent_without_proven_parent"
        elif self.scope and any(_dotted(d) for d in node.decorator_list):
            relation, detail = "DECORATED_EXTERNAL_UNRESOLVED", "nested_or_dynamic_decorator"
        self._add(node, node.name, "method" if cls is not None else "function",
                  relation=relation, detail=detail)
        self.scope.append(node.name)
        params = (
            node.args.posonlyargs + node.args.args + node.args.kwonlyargs
        )
        if node.args.vararg:
            params.append(node.args.vararg)
        if node.args.kwarg:
            params.append(node.args.kwarg)
        for param in params:
            if param.arg in ("self", "cls"):
                continue
            self._add(param, param.arg, "parameter")
        for stmt in node.body:
            self.visit(stmt)
        self.scope.pop()

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        cls = self.classes.get(self.scope[0]) if len(self.scope) == 1 else None
        if cls is None or not isinstance(node.target, ast.Name):
            return
        name = node.target.id
        tag, mapping = self._field_alias(node.value)
        if tag == "literal":
            relation, detail = "DTO_FIELD_ALIAS_DECLARED", mapping or ""
        elif tag == "unknown":
            relation, detail = "DTO_FIELD_MAPPING_UNRESOLVED", "dynamic_mapping"
        elif self._dto(cls):
            relation, detail = "DTO_DIRECT_FIELD_UNRESOLVED", "external_field_contract_unknown"
        else:
            relation, detail = "LOCAL", ""
        self._add(node.target, name, "field", relation, detail)

    def visit_Assign(self, node: ast.Assign) -> None:
        cls = self.classes.get(self.scope[0]) if len(self.scope) == 1 else None
        if cls is None:
            return
        if len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            tag, mapping = self._field_alias(node.value)
            if tag == "literal":
                self._add(node.targets[0], node.targets[0].id, "field",
                          "DTO_FIELD_ALIAS_DECLARED", mapping or "")
            elif tag == "unknown":
                self._add(node.targets[0], node.targets[0].id, "field",
                          "DTO_FIELD_MAPPING_UNRESOLVED", "dynamic_mapping")


def extract_python_naming(
    parsed: ParsedSnapshot, sources: Mapping[str, str], *, snapshot_id: str,
) -> NamingEvidence:
    """Collect declarations from exact parsed UTF-8 bytes only."""
    if not isinstance(snapshot_id, str) or not snapshot_id:
        raise ValueError("source snapshot identity required")
    if set(sources) != (
        set(parsed.analyzed_paths) | {path for path, _ in parsed.unprocessed}
    ) or any(not isinstance(p, str) or not isinstance(v, str) or not p
             or p.startswith("/") or "\\" in p or ".." in p.split("/")
             for p, v in sources.items()):
        raise ValueError("invalid source inventory or selection")
    symbols = []
    for file in parsed.files:
        if file.tree is None or sha256(sources[file.path].encode()).hexdigest() != file.digest:
            raise ValueError("stale parsed source evidence")
        module_name = file.path.rsplit("/", 1)[-1][:-3]
        if module_name != "__init__":
            symbols.append(NamingSymbol(
                file.path, "", module_name, "module", 1, 0, "LOCAL", None,
                "module_filename",
            ))
        collector = _Declarations(file.path, file.tree)
        collector.visit(file.tree)
        symbols.extend(collector.entries)
    return NamingEvidence(
        snapshot_id=snapshot_id,
        analyzed_paths=tuple(sorted(parsed.analyzed_paths)),
        unprocessed=tuple(sorted(parsed.unprocessed)),
        source_sha256=tuple(sorted((path, sha256(text.encode()).hexdigest())
                                    for path, text in sources.items())),
        symbols=tuple(sorted(symbols, key=lambda x: (
            x.path, x.line, x.column, x.kind, x.owner, x.name
        ))),
    )
