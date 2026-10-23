"""AST-independent evidence transport for optional Python P6 complexity review."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ControlFlowObservation:
    node_id: str
    path: str
    start_line: int
    end_line: int
    decision_count: int | None
    cyclomatic_proxy: int | None
    branch_nesting_max: int | None
    limitations: tuple[str, ...]
    status: str   # MEASURED | NOT_EVALUATED
    producer: str = "python-ast-complexity-v0.1"
    method: str = "bounded_python_ast_syntax"

    def to_document(self) -> dict[str, Any]:
        return asdict(self)
