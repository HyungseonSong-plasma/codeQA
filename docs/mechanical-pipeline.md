# Mechanical QA v0.1 and Python analysis pipeline

The \`codeqa.pipeline.python.analyze_python\` function composes the Python
syntax Adapter, CCG v0.1 Core validation and limited mechanical evaluation.

\`\`\`python
from codeqa.pipeline.python import analyze_python
from codeqa.infrastructure.resources import ResourceRegistry

registry = ResourceRegistry(codeqa_repository_root)
result = analyze_python(
    {"source.py": "def example():\n    pass\n"},
    snapshot_id="the-pinned-input-revision",
    ccg_schema=registry.load_json("ccg_schema"),
    mechanical_profile=registry.load_json("mechanical_profile"),
)
document = result.to_document()
\`\`\`

Callers own **source acquisition and immutable snapshot identity**.
The Pipeline never imports source files, reads repository trees, runs code, or
performs GitHub mutation. External Samuel/David orchestration remains external.

## Current evidence-based signals

- **Function size**: measured line span against the explicit
  \`max_function_lines\` profile threshold. It is a review heuristic related to
  P1 (SRP), **not** proof of SRP violation.
- **Outgoing call sites**: count syntax-observed call sites in function/method
  scopes against \`max_call_sites\`. It is a review heuristic related to P3
  (low coupling), **not** proof of excessive coupling.
- **Missing information**: unresolved graph edges, partial parsing and missing
  function-span evidence prevent a confident mechanical PASS.
- **Coverage none** yields \`NOT_EVALUATED\`; with parsed input but no
  functions, \`not_evaluated\` identifies the missing applicable scope.

\`PASS\` means *only these v0.1 signals had adequate evidence and raised no
review requirement*. It **does not** mean P1–P8 compliance or overall code
quality approval. \`REVIEW_REQUIRED\` identifies uncertainty or threshold
signals without claiming a defect. \`FAIL\` is reserved for future provable
rules; this evaluator never invents it.

Policy values live in \`profiles/\` and are loaded through the logical
\`mechanical_profile\` ID. The report is currently an **internal Python
structure**, not yet a versioned external Quality Report Contract.
