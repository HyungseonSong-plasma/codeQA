# Python Naming MVP product boundary v0.1 (#120)

The **default** `codeqa.pipeline.python.analyze_python` analyzes Python AST,
CCG and conservative Mechanical P1/P3 evidence. It does **not** run Naming,
change the public QA Result v0.1 contract, or certify external interfaces.

For an explicit, separate Naming v0.1 spelling review:

```python
from codeqa.pipeline.naming_product import analyze_python_naming_opt_in
from codeqa.infrastructure.resources import ResourceRegistry

resources = ResourceRegistry(codeqa_repository_root)
report = analyze_python_naming_opt_in(
    {"sample.py": "class Thing:\n    def BadMethod(self): pass\n"},
    snapshot_id="immutable-snapshot-id",
    naming_profile=resources.load_json("python_naming_safe_profile"),
)
print(report.status)  # REVIEW_REQUIRED: spelling observation only
```

The opt-in path composes existing Python AST naming evidence, the safe profile
and the existing `evaluate_naming` evaluator; it does not replace or change
them. A `NO_VIOLATIONS_OBSERVED` spelling result is not a semantic PASS.
Unresolved external bases, SDK dispatch, DTO/ORM effective aliases and
unapproved **broader** glossary scopes remain `NOT_EVALUATED`. The distinct official
v0.5 opt-in covers only `ControlFlowObservation.node_id` at its pinned declaration;
it does not change the safe v0.1 spelling analyzer or its default activation.

| Capability | Activation | Authority / remaining evidence |
| --- | --- | --- |
| Python safe declaration spelling v0.1 | Explicit opt-in function and registered profile | Source spelling review, not interface proof |
| Python naming coverage v0.2, pinned ancestors, directional fields | Separate opt-in companion APIs/profiles | Experimental, exact source witnesses only |
| Naming glossary, source delta, rename-impact proposal | Separate opt-in/manual paths | The official Naming v0.5 scope covers only one approved internal field; broader glossary semantics, rename safety and public compatibility remain unverified (#144/#94) |
| Real external SDK/typechecker/DTO/ORM | Separate pinned tests and evidence (#92) | Synthetic tests do not prove public API or DB migration |
| Rust parser and C++/MOOSE framework Naming | Manual/fixture evidence (#93) | Production ABI/DSL evidence not established |
| Formal generated fixture | Separate `ALLOW_FIXTURE_ONLY` Gate (#102) | Not a Naming PASS or production authorization |

The existing `tests/test_naming_product_boundary.py` exercises a real
Mechanical-before/after equality witness and separate opt-in Naming report,
plus unresolved external and invalid profile negatives. It is not a user
study or human glossary approval. Do not silently enable experimental
companions or conflate Mechanical P1/P3 with Naming v0.3.

The additional `test_naming_public_qa_isolation.py` converts Mechanical evidence
to the frozen Public QA Result v0.1 before and after explicitly invoking safe
Naming on real Python AST fixtures. It asserts byte-identical canonical public
QA JSON, unchanged unsupported-rule coverage, and separate Naming review.
This is a controlled test, not production SDK or independently reviewed
Naming glossary evidence.
