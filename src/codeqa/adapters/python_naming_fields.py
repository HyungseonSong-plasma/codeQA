"""Conservative Python AST field alias extraction against caller-pinned schema."""
from __future__ import annotations

import ast
from hashlib import sha256
import json
from collections.abc import Mapping

from codeqa.core.naming_fields import (
    DIRECTIONS, DirectionalFieldEvidence, DirectionalFieldWitness,
    FieldMappingError, FieldMappingProfile,
)
from .python_snapshot import ParsedSnapshot


def _dotted(n: ast.AST) -> str | None:
    if isinstance(n, ast.Name):
        return n.id
    if isinstance(n, ast.Attribute):
        stem=_dotted(n.value)
        return stem+"."+n.attr if stem else None
    return None


def _imports(tree: ast.Module) -> dict[str,str]:
    resolved: dict[str,str]={}
    shadowed=set()
    for node in tree.body:
        aliases=[]
        if isinstance(node,ast.Import):
            aliases=[(a.asname or a.name.split(".")[0],a.name if a.asname else a.name.split(".")[0])
                     for a in node.names]
        elif isinstance(node,ast.ImportFrom) and node.module and node.level==0:
            aliases=[(a.asname or a.name,node.module+"."+a.name)
                     for a in node.names if a.name!="*"]
        for alias,qualified in aliases:
            if alias in resolved:
                shadowed.add(alias)
            resolved[alias]=qualified
        if isinstance(node,(ast.ClassDef,ast.FunctionDef,ast.AsyncFunctionDef)):
            shadowed.add(node.name)
        if isinstance(node,ast.Assign):
            for target in node.targets:
                if isinstance(target,ast.Name):
                    shadowed.add(target.id)
    return {k:v for k,v in resolved.items() if k not in shadowed}


def _mapping(node: ast.AST | None, imports: dict[str,str]) -> tuple[dict[str,str|None],str,str]:
    declared={x:None for x in DIRECTIONS}
    if not isinstance(node,ast.Call):
        return declared,"unresolved","no_explicit_field_mapping"
    name=_dotted(node.func)
    if not name:
        return declared,"unresolved","dynamic_field_constructor"
    root,*other=name.split(".")
    qualified=".".join((imports.get(root,root),*other))
    if qualified in ("pydantic.Field","pydantic.fields.Field"):
        kw={x.arg:x.value for x in node.keywords if x.arg is not None}
        if any(x.arg is None for x in node.keywords):
            return declared,"pydantic.Field","dynamic_keyword_expansion"
        raw={}
        for direction,key in (("input","validation_alias"),("output","serialization_alias")):
            raw[direction]=kw.get(key,kw.get("alias"))
        for direction,value in raw.items():
            if isinstance(value,ast.Constant) and isinstance(value.value,str):
                declared[direction]=value.value
        return declared,"pydantic.Field","serializer_config_and_runtime_alias_not_verified"
    if qualified in ("sqlalchemy.orm.mapped_column","sqlalchemy.mapped_column"):
        if node.args and isinstance(node.args[0],ast.Constant) and type(node.args[0].value) is str:
            declared["database"]=node.args[0].value
        return declared,"sqlalchemy.mapped_column","database_schema_and_column_key_not_verified"
    return declared,"unresolved","unrecognized_field_mapping_constructor"


def extract_python_directional_fields(
    parsed: ParsedSnapshot, sources: Mapping[str,str],
    contract_source: str, *, snapshot_id: str,
    profile: FieldMappingProfile,
) -> DirectionalFieldEvidence:
    if not isinstance(profile,FieldMappingProfile) or not snapshot_id:
        raise FieldMappingError("invalid snapshot/profile identity")
    scope=set(parsed.analyzed_paths)|{p for p,_ in parsed.unprocessed}
    if (set(sources)!=scope or any(not isinstance(x,str) for x in sources.values())
            or not isinstance(contract_source,str)
            or sha256(contract_source.encode()).hexdigest()!=profile.schema_sha256):
        raise FieldMappingError("selected source inventory or contract digest drift")
    try:
        contract=json.loads(contract_source)
    except json.JSONDecodeError as exc:
        raise FieldMappingError("invalid pinned JSON contract") from exc
    if (not isinstance(contract,dict) or set(contract)!=
            {"provider","revision","models"}
            or contract["provider"]!=profile.provider
            or contract["revision"]!=profile.revision
            or not isinstance(contract["models"],dict)):
        raise FieldMappingError("wrong external schema identity or shape")
    model_expectations={}
    for binding in profile.bindings:
        try:
            expected=contract["models"][binding.schema_model][binding.field]
        except (KeyError,TypeError) as exc:
            raise FieldMappingError("missing exact field in pinned external schema") from exc
        if (not isinstance(expected,dict) or not expected or
                any(direction not in DIRECTIONS or
                    not isinstance(value,str) or not value
                    for direction,value in expected.items())):
            raise FieldMappingError("ambiguous/dynamic external field schema key")
        model_expectations[(binding.path,binding.owner,binding.field)]=tuple(sorted(expected.items()))
    found={}
    for parsed_file in parsed.files:
        if parsed_file.tree is None or sha256(sources[parsed_file.path].encode()).hexdigest()!=parsed_file.digest:
            raise FieldMappingError("parsed source hash drift")
        imported=_imports(parsed_file.tree)
        for cls in parsed_file.tree.body:
            if not isinstance(cls,ast.ClassDef):
                continue
            for item in cls.body:
                if isinstance(item,ast.AnnAssign) and isinstance(item.target,ast.Name):
                    attr,expr=item.target,item.value
                elif (isinstance(item,ast.Assign) and len(item.targets)==1
                      and isinstance(item.targets[0],ast.Name)):
                    attr,expr=item.targets[0],item.value
                else:
                    continue
                key=(parsed_file.path,cls.name,attr.id)
                if key not in model_expectations:
                    continue
                if key in found:
                    raise FieldMappingError("duplicated source field declaration")
                values,mechanism,reason=_mapping(expr,imported)
                found[key]=DirectionalFieldWitness(
                    parsed_file.path,cls.name,attr.id,attr.lineno,attr.col_offset,
                    "python-ast-directional-field-v0.1",
                    tuple(sorted(values.items())),model_expectations[key],
                    mechanism,reason,
                )
    missing=tuple(sorted(k for k in model_expectations if k not in found))
    return DirectionalFieldEvidence(
        snapshot_id=snapshot_id,profile_fingerprint=profile.fingerprint(),
        source_sha256=tuple(sorted((p,sha256(v.encode()).hexdigest())
                                   for p,v in sources.items())),
        schema_sha256=profile.schema_sha256,
        witnesses=tuple(sorted(found.values(),key=lambda x:(x.path,x.owner,x.name))),
        skipped_contracts=missing,
    )
