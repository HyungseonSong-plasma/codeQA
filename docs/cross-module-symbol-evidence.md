# Conservative cross-module symbol declaration evidence

## Motivation

The last moose-test-repo report showed 129 product call-volume
warnings and syntactic AST context for all 129. An imported namespace or a
fluent-looking expression, however, is not a runtime dependency identity.
This stage adds a **non-scoring companion** for simple call sites where the
source declaration behind an explicit import is identifiable.

## Precisely supported cases

1. From-import of a plain top-level function in a unique source module
   (e.g. from pkg.core import helper as h; h()).
2. Explicit aliased module import of a unique source module with a plain
   module-level function (e.g. import pkg.core as m; m.helper()).
3. Unique exact Python module path in analyzed snapshot, including supported
   relative imports.
4. Only calls within direct top-level Python function bodies, excluding
   nested functions, classes, lambdas and unresolved dynamic scopes.
5. Only unambiguous import bindings without local/global rebinding, wildcards
   or ambiguous module paths. Target function declarations must be unique,
   undecorated and not rebound.

Every candidate has an exact source call location, an immutable evidence ID,
an imported module path, a target declaration Node ID and an explicit
STATIC_DECLARATION_CANDIDATE_NOT_RUNTIME_TARGET assurance marker.

The imported runtime object, module cache, monkey-patches, import hooks,
re-exports, bound methods, attribute descriptors, class dispatch and
dependency injection remain unknown. No cross-module CCG edge is upgraded
to resolved based on these candidate links.

## Report contract (internal and non-scoring)

The Python pipeline now exports a separate symbol_calls detail section,
plus a summary of scanned top-level function calls, candidate site count,
and exclusions by reason. Existing contextual_review findings also expose
cross_file_declaration_candidates. These **do not** change Mechanical v0.1
status, call thresholds, finding count, CCG v0.1 or impact safety semantics.

The pinned moose-test-repo external read-only audit additionally publishes
candidate counts, distinct source/target function pairs, skipped reasons
and a small set of source-grounded examples. The previous CCG and
Mechanical totals are checked on the same fixed commit SHA.

## What remains for complex contextual QA

- **Runtime symbol resolution**: needs explicit runtime evidence, never
  inferred merely from import syntax.
- **Verified DSL semantics**: needs a versioned, library-specific registry
  with provenance and negative cases. Importing polars as pl alone is not
  evidence that a subsequent chained object is a Polars Expr.
- **Domain and scientific contract**: needs declared source of truth for
  MOOSE input contracts, conservation laws and validated invariants. A
  filename or function name is not enough.
- **Test relevance**: needs function-to-test coverage, fixture ownership and
  explicit behavior/entrypoint mappings; static import paths alone cannot
  certify any test irrelevant.
- **Report governance**: before external consumers rely on these details,
  version a stable report schema and give separate assessed / unassessed /
  observed states to avoid blending heuristics and contract failures.

Do not turn these unproven layers into a coupling score. Maintain the
One Parse -> Shared Evidence -> Separate Evaluations -> Unified Report
architecture and keep codeQA language-neutral boundaries intact.
