# Responsibility & Behavior v0.1 — syntax-backed triage

This companion analysis matches a **small, explicit registry of imported API call signatures** to declared directory responsibilities. It is not a runtime behavior analyzer, cannot prove side effects, and never turns a matching API name into a full semantic role PASS.

## Data contracts and architecture

- `profiles/responsibility-behavior-v0.1.json` defines reviewed `module.symbol` call syntaxes and the role exclusions for `src/codeqa`.
- `core/behavior.py`: language-neutral `BehaviorObservation`, `BehaviorPlacement`, `ResponsibilityBehaviorReport`.
- `adapters/python_behavior.py`: observes exact AST call shapes using the already parsed snapshot and EvidenceIndex. No source is imported or executed.
- `evaluation/responsibility_behavior.py`: validates catalog versus directory roles and compares *observations* with *declared exclusions*; no Python AST import here.
- `contracts/semantic/responsibility-behavior-v0.1.schema.json`: separate versioned report envelope. The immutable CCG v0.1 and Semantic Architecture v0.1 contracts are unchanged.
- `pipeline/python.py`: optional `behavior_policy` alongside `semantic_policy`.

## Supported observations

`import ast; ast.walk(...)` and `ast.parse(...)`, and explicit aliases such as `import ast as syntax` or `from ast import parse as parse_source` are classified `AST_SOURCE_INTERPRETATION_SYNTAX`. Unique `subprocess.run`, `subprocess.Popen`, and `subprocess.check_output` declarations are classified `PROCESS_INVOCATION_SYNTAX`.

**This only proves the syntax of a declared imported API call**. It does not prove that a library was successfully imported, that the call occurred at runtime, that a process spawned, or that the result was used. Monkeypatching or dynamic dispatch can change runtime behavior.

Potentially shadowed import names, multiple import declarations of the same bound name, dotted imports without an exact alias, missing source witnesses and dynamic method calls are excluded conservatively. Function body observations keep source Node IDs and exact call-line/column Evidence IDs; nested functions are attributed separately, and lambda bodies are not scored.

## Interpretation

| Output | Meaning |
|---|---|
| `ROLE_CONFLICT_REVIEW` | A declared role explicitly excludes the observed imported API call syntax; **manual investigation required**, not certified violation |
| `ROLE_COMPATIBLE_OBSERVATION` | No explicit exclusion for this particular syntax; **not** a statement that the function is correctly owned |
| `NOT_EVALUATED` | No verified semantic completeness, even if compatible observations exist |
| `REVIEW_REQUIRED` | One or more evidence-backed, syntactic conflicts warrant review |

Absence of observed calls never proves absence of behavior. Evaluated cases do **not** clear `behavior_vs_responsibility` as an unassessed global Semantic Architecture dimension. Direct/transitive effects, method dispatch, dependency injection, DSL or MOOSE scientific meaning all remain explicitly unassessed.

## Ground Truth and boundaries

Tests cover unshadowed aliases, from-import aliases, AST/process syntax, forbidden roles, local/parameter rebinding, dotted imports, duplicate names, nested scopes, dynamic fluent-looking method calls, deterministic serialization, policy misconfiguration, and unchanged legacy reports. Each new behavior catalog entry requires verified positive **and adversarial** examples before adding a role rule.

CodeQA's existing GitHub semantic-layout audit emits a separate `responsibility_behavior` JSON view. It does not fail CI merely for a `ROLE_CONFLICT_REVIEW`; policy owners must first validate the behavior assignment. It continues to fail known forbidden static directory-role edges.
