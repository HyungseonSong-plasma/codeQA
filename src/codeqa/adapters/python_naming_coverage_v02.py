"""Additional Python naming declarations, never runtime- or import-resolved."""
from __future__ import annotations

import ast
from collections.abc import Mapping
from hashlib import sha256

from codeqa.core.naming_coverage_v02 import (
    NamingExtendedEvidence, NamingExtendedSymbol, NamingUncertainty,
)
from .python_snapshot import ParsedSnapshot


def _dotted(n: ast.AST) -> str | None:
    if isinstance(n, ast.Name):
        return n.id
    if isinstance(n, ast.Attribute):
        prefix=_dotted(n.value)
        return prefix+"."+n.attr if prefix else None
    return None


def _imports(tree: ast.Module) -> dict[str, str]:
    bindings: dict[str,str]={}
    conflicting=set()
    for node in tree.body:
        if isinstance(node,ast.Import):
            for alias in node.names:
                local=alias.asname or alias.name.split(".")[0]
                if local in bindings:
                    conflicting.add(local)
                bindings[local]=alias.name if alias.asname else local
        if isinstance(node,ast.ImportFrom) and node.level==0 and node.module:
            for alias in node.names:
                if alias.name=="*":
                    continue
                local=alias.asname or alias.name
                if local in bindings:
                    conflicting.add(local)
                bindings[local]=node.module+"."+alias.name
        if isinstance(node,(ast.ClassDef,ast.FunctionDef,ast.AsyncFunctionDef)):
            conflicting.add(node.name)
        if isinstance(node,(ast.Assign,ast.AnnAssign)):
            targets=node.targets if isinstance(node,ast.Assign) else [node.target]
            conflicting.update(t.id for t in targets if isinstance(t,ast.Name))
    return {k:v for k,v in bindings.items() if k not in conflicting}


class _Extra(ast.NodeVisitor):
    def __init__(self, path: str, source: str, tree: ast.Module):
        self.path=path
        self.source=source
        self.imports=_imports(tree)
        self.scope: list[str]=[]
        self.classes: list[ast.ClassDef]=[]
        self.decls: list[NamingExtendedSymbol]=[]
        self.unknowns: list[NamingUncertainty]=[]
        self.seen=set()

    def unknown(self, node: ast.AST, category: str, reason: str)->None:
        self.unknowns.append(NamingUncertainty(
            self.path,".".join(self.scope),node.lineno,category,reason))

    def is_final(self, annotation: ast.AST)->bool:
        expr=annotation.value if isinstance(annotation,ast.Subscript) else annotation
        name=_dotted(expr)
        if not name:
            return False
        first,*rest=name.split(".")
        name=".".join((self.imports.get(first,first),*rest))
        return name in ("typing.Final","typing_extensions.Final")

    def declare(self, node: ast.Name | ast.Attribute, name: str,
                kind: str, relation: str, reason: str)->None:
        column=node.col_offset
        if isinstance(node,ast.Attribute):
            column=node.end_col_offset-len(name.encode("utf-8"))
        identity=(self.path,".".join(self.scope),name,kind)
        if identity in self.seen:
            self.unknown(node,"repeated_assignment","same_lexical_identifier_seen_more_than_once")
            return
        self.seen.add(identity)
        self.decls.append(NamingExtendedSymbol(
            self.path,".".join(self.scope),name,kind,node.lineno,
            column,relation,reason))

    def visit_ImportFrom(self,node:ast.ImportFrom)->None:
        if node.level or not node.module or any(x.name=="*" for x in node.names):
            self.unknown(node,"import_binding","relative_or_wildcard_import_not_resolved")

    def visit_AnnAssign(self,node:ast.AnnAssign)->None:
        if len(self.scope)<=1 and isinstance(node.target,ast.Name):
            if self.is_final(node.annotation):
                self.declare(node.target,node.target.id,
                             "class_constant" if self.scope else "module_constant",
                             "DECLARED_FINAL","typing_final_annotation_intent_only")
            elif node.target.id.isupper():
                self.unknown(node,"constant_intent",
                             "uppercase_assignment_is_not_a_proven_immutable_constant")
        self.generic_visit(node)

    def visit_Assign(self,node:ast.Assign)->None:
        if len(self.scope)<=1:
            for target in node.targets:
                if isinstance(target,ast.Name) and target.id.isupper():
                    self.unknown(node,"constant_intent",
                                 "unannotated_uppercase_binding_not_proven_constant")
        self.generic_visit(node)

    def visit_ClassDef(self,node:ast.ClassDef)->None:
        self.scope.append(node.name)
        self.classes.append(node)
        if len(self.scope)>1:
            self.unknown(node,"nested_class",
                         "nested_class_lexical_role_only_not_complete_binding")
        if node.decorator_list:
            self.unknown(node,"decorator_binding",
                         "class_decorator_effect_not_evaluated")
        for stmt in node.body:
            self.visit(stmt)
        self.classes.pop()
        self.scope.pop()

    def visit_FunctionDef(self,node:ast.FunctionDef|ast.AsyncFunctionDef)->None:
        self.scope.append(node.name)
        if len(self.scope)>2 or (len(self.scope)>1 and not self.classes):
            self.unknown(node,"nested_declaration",
                         "nested_function_or_method_binding_not_verified")
        if node.decorator_list:
            self.unknown(node,"decorator_binding",
                         "function_decorator_effect_not_evaluated")
        is_init=(bool(self.classes) and len(self.scope)==2
                 and node.name=="__init__" and
                 bool(node.args.args) and node.args.args[0].arg=="self")
        if is_init:
            for statement in node.body:
                nodes=[]
                if isinstance(statement,(ast.Assign,ast.AnnAssign)):
                    targets=statement.targets if isinstance(statement,ast.Assign) else [statement.target]
                    nodes=[t for t in targets if isinstance(t,ast.Attribute)]
                for attr in nodes:
                    if isinstance(attr.value,ast.Name) and attr.value.id=="self":
                        # Source assignments in __init__ are not guaranteed
                        # instance storage (descriptors, __setattr__, etc.).
                        if self.classes[-1].bases or self.classes[-1].keywords:
                            rel,reason="UNRESOLVED_SOURCE","inherited_attribute_or_setattr_unknown"
                        else:
                            rel,reason="ASSIGNMENT_IN_INIT","direct_self_attribute_syntax_only"
                        self.declare(attr,attr.attr,"instance_attribute",rel,reason)
        for statement in node.body:
            if isinstance(statement,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)):
                self.visit(statement)
            elif isinstance(statement,(ast.Assign,ast.AnnAssign)):
                pass
            else:
                # Do not make unsupported nested/lambda writes into declarations.
                for descendant in ast.walk(statement):
                    if (isinstance(descendant,ast.Call) and isinstance(descendant.func,ast.Name)
                            and descendant.func.id in ("setattr","exec","eval","globals","locals")):
                        self.unknown(descendant,"dynamic_binding",
                                     "dynamic_source_binding_not_resolved")
                    if isinstance(descendant,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)):
                        self.unknown(descendant,"nested_binding",
                                     "conditional_or_nested_lexical_declaration")
        self.scope.pop()

    visit_AsyncFunctionDef=visit_FunctionDef


def extract_python_extended_naming(
    parsed:ParsedSnapshot,sources:Mapping[str,str],*,snapshot_id:str,
)->NamingExtendedEvidence:
    if not isinstance(snapshot_id,str) or not snapshot_id:
        raise ValueError("immutable source identity required")
    expected=set(parsed.analyzed_paths)|{p for p,_ in parsed.unprocessed}
    if (set(sources)!=expected or any(not isinstance(p,str) or not isinstance(s,str)
            or not p or p.startswith("/") or "\\" in p or ".." in p.split("/")
            for p,s in sources.items())):
        raise ValueError("invalid selected source inventory")
    declared=[]
    unknown=[]
    for file in parsed.files:
        if file.tree is None or sha256(sources[file.path].encode()).hexdigest()!=file.digest:
            raise ValueError("stale source hash or AST evidence")
        collector=_Extra(file.path,sources[file.path],file.tree)
        collector.visit(file.tree)
        declared.extend(collector.decls)
        unknown.extend(collector.unknowns)
    return NamingExtendedEvidence(
        snapshot_id,
        tuple(sorted((path,sha256(s.encode()).hexdigest()) for path,s in sources.items())),
        tuple(sorted(parsed.analyzed_paths)),
        tuple(sorted(parsed.unprocessed)),
        tuple(sorted(declared,key=lambda x:(x.path,x.line,x.column,x.kind,x.name))),
        tuple(sorted(unknown,key=lambda x:(x.path,x.line,x.category,x.reason))),
    )
