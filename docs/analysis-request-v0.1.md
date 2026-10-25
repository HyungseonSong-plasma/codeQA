# Optional Python AnalysisRequest v0.1 (#123)

This **additive** API does not change the existing
`codeqa.pipeline.python.analyze_python` signature or its default CCG,
Mechanical P1/P3, unified summary or public QA Result v0.1. It is not a new
universal QA contract. Use an explicit, typed request when caller-controlled
optional companion activation and a stable options fingerprint are useful.

```python
from codeqa.pipeline.analysis_request import (
    AnalysisRequest, AnalysisOptions, analyze_python_request,
)
from codeqa.infrastructure.resources import ResourceRegistry

resources = ResourceRegistry(codeqa_repository_root)
request = AnalysisRequest(
    sources={"a.py": "def f(): return 1\n"}, snapshot_id="pinned-source-id",
    ccg_schema=resources.load_json("ccg_schema"),
    mechanical_profile=resources.load_json("mechanical_profile"),
)
result = analyze_python_request(request)
print(result.summary_document()["companion_states"])
```

For explicit static reverse-import impact, pass
`options=AnalysisOptions.from_mapping({"changed_paths": ["a.py"]})`.
Optional `semantic_policy` and `behavior_policy` use the existing policy
validators; absent stages report `NOT_REQUESTED`. Unsupported or unknown
option names fail closed. Naming v0.1 remains a **separate** opt-in API (#120);
Formal fixture and external Evidence Gate also remain separate. They cannot
be enabled by a Boolean flag or silently promoted to a Mechanical PASS.

The new `AnalysisResponse.summary_document()` is a wrapper with an options
SHA-256 fingerprint and explicit companion states, **not** a replacement for
frozen `QA Result v0.1`. Default before/after equality and adversarial
option negatives are exercised in `tests/test_analysis_request.py`.
The existing isolated Python wheel/sdist smoke now also exercises an explicit
impact-bearing AnalysisRequest and verifies unchanged Mechanical output on the
installed package (subject to exact-head CI). Independently reviewed public
request serialization compatibility remains `NOT_EVALUATED`.
