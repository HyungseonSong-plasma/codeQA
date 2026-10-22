"""Language-neutral immutable function call-syntax evidence record.

Field categories describe observed source syntax, not runtime call identity.
Language adapters populate primitive fields; Evaluation consumes the contract
without importing language-specific parser types or AST nodes.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class FunctionSyntaxContext:
    node_id: str
    call_sites: int
    name_calls: int
    attribute_calls: int
    chained_attribute_calls: int
    other_calls: int
    distinct_callee_syntax: int
    frequent_callee_syntax: tuple[tuple[str, int], ...]
    declared_import_namespace_hints: tuple[tuple[str, str, int], ...]
    branch_constructs: int
    loop_constructs: int
    try_constructs: int
    raise_statements: int
    return_statements: int
    call_expression_nesting_max: int
    interpretation: str = "SYNTAX_ONLY"

    def to_document(self) -> dict[str, Any]:
        return asdict(self)
