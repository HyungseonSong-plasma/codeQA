# Python control-flow complexity companion v0.1 (#37)

**Scope:** Opt-in static Python 3.12 AST measurements over a caller-supplied
immutable source snapshot; no target import/execution, Git access or
automatic P6 simplicity verdict. The adapter consumes the already parsed
`ParsedSnapshot` and creates language-neutral
`codeqa.core.complexity.ControlFlowObservation` records; the pure evaluator
takes a validated CCG graph and a versioned `complexity_profile`.
Public report schema: `complexity_report_schema`, separate from frozen CCG,
Mechanical v0.1 and QA Result v0.1.

## Precisely defined metrics

- `decision_count` is a **syntactic decision proxy**: one for `if`,
  `elif`, `if` expression, `for`/`async for`/`while`; one for each
  `except`/`except*` handler; `n-1` for `match` case alternatives;
  `len(values)-1` for `and/or` Boolean operators; one per comprehension
  generator plus one per comprehension `if`.
- `cyclomatic_proxy = 1 + decision_count`. It is **not** a full CFG-derived
  McCabe complexity or a cognitive-complexity score; short-circuit decisions
  and exception paths are included by explicit syntax rules.
- `branch_nesting_max` counts nested syntactic decision *bodies*, starting
  at zero. `elif` AST nesting is counted as nested `if`. `else` and
  `finally` do not independently add decisions. Boolean operators do not
  increase nesting. Complex numerical logic may legitimately exceed bounds.
- Nested function and method definitions are scored **independently**;
  nested classes do not contribute to an enclosing function score. Async
  function bodies are counted under the same rules; `await` is not a branch.
- Decorators, default arguments, annotation/signature expressions and
  lambda bodies are **excluded** from scoring. If present, the function is
  `NOT_EVALUATED` with a concrete reason and null numeric metrics. Partial
  or unparsed files remain explicit coverage, never zero complexity.
- Thresholds live in the opt-in versioned profile
  `profiles/complexity-v0.1.json`. Exceeding either threshold yields
  `REVIEW_REQUIRED`; it does **not** prove a P6 simplicity defect.

Example usage:

```python
from codeqa.adapters.python_snapshot import parse_python_snapshot
from codeqa.adapters.python import adapt_parsed_python
from codeqa.adapters.python_complexity import extract_python_complexity
from codeqa.evaluation.complexity import ComplexityProfile, evaluate_complexity

parsed = parse_python_snapshot(sources)
graph = adapt_parsed_python(parsed, snapshot_id=immutable_sha, schema=ccg_schema)
facts = extract_python_complexity(parsed)
review = evaluate_complexity(graph, facts, ComplexityProfile.from_mapping(profile))
```

The comparison is source-scoped and deterministic. No latent complexity
result is inserted into old `PythonAnalysis.to_document()`; a separately
versioned report schema is provided for validation and future API extension.
Tests cover matching CCG node/line identity, nested/async functions, branching,
match, exception handling, comprehensions, decorators, lambdas, partial parse,
profile drift and non-alteration of existing Mechanical results.
