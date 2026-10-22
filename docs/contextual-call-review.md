# Context-aware call-site reporting (non-scoring v0.1 companion)

## Why the original rule was misleading

Mechanical v0.1 flags functions with more than 12 AST `Call` nodes. That
counts `pl.col()`, `.sum()`, `.alias()` and `.collect()` independently:
it measures source expression density, **not coupling** or distinct runtime
dependencies. The rule is preserved for compatibility, and no historical
findings are silently suppressed or changed.

## New measured syntax facts

Per function, the same parsed Python AST now supplies `function_context`:

- `name_calls` for direct name-shaped calls.
- `attribute_calls` for attribute-shaped calls with non-Call receivers.
- `chained_attribute_calls` when a call has an attribute callee whose
  receiver is itself an AST call; this is a syntactic *chain*, not a
  verified Polars/fluent API or known runtime target.
- `other_calls`, `distinct_callee_syntax`, and the eight most frequently
  observed callee expressions.
- counts of syntactic branch/loop/try/raise/return constructs and maximum
  nested-call depth. None of these are a verified cognitive complexity score.

New `contextual_review` annotates only original `outgoing_call_sites_review`
findings. Every review retains the original call site count, threshold,
confirmed local target count and unresolved call-site count, while adding
syntax counts, repeated-expression evidence and non-scoring context flags.
Flags are heuristic **descriptions**, not suppression or P3 pass/fail.

`ATTRIBUTE_SYNTAX_DOMINANT` indicates >=75% of call sites have attribute-shaped
callees. `CHAINED_ATTRIBUTE_SYNTAX` indicates >=3 chained calls.
`REPEATED_CALLEE_SYNTAX` indicates call count at least twice the number
of distinct syntactic callees. `RUNTIME_TARGETS_UNVERIFIED` and
`CONTROL_FLOW_PRESENT` disclose separate uncertainty and control evidence.

## Exact same-source before/after interpretation

The external moose-test audit is pinned to target SHA
`1977ad5559e5aa7a1c8d04c83735c15e007130d5`.
The workflow asserts historical counts for all six source scopes.
Changes to *contextual* observations are newly added columns; the legacy
CCG/Mechanical counts remain unchanged. This is not a claim that fewer
bugs or coupling defects exist. Scope partitioning matters: experiment
files do not automatically count as current product logic.

## Context still required for sound semantic conclusions

| Context dimension | Currently supported | Next prerequisite |
|---|---|---|
| Source provenance and call syntax | Yes, exact AST observations | None |
| Local lexical targets | Conservative subset | True symbol/import aliases |
| Declarative DSL / Polars fluent identity | No | Verified library binding and schema-aware DSL catalog |
| Data flow and side effects | No | Safe interprocedural effect summaries |
| Architectural and scientific contracts | No | Explicit versioned domain contract facts |
| Test-to-change relevance | Static import paths only | Test ownership, fixture/entrypoint mapping |
| Runtime dispatch / dynamic imports | No | Runtime evidence, separately labeled |

Do not infer verified DSL identity merely from an attribute named `col`,
`alias`, or `sum`; unrelated objects can use these names. An unsupported
context must be `unknown`/`NOT_EVALUATED` rather than guessed. Extend
source evidence facts, version the report contract before public consumers,
and require ground truth with positive and adversarial examples for each
future semantic layer.
