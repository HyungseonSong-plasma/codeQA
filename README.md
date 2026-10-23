# codeQA

A language-independent, evidence-based code quality evaluation system.

## codeQA-init — Samuel capability-ready bootstrap

Run `codeQA-init` using the canonical [consumer bootstrap](docs/operating_system/BOOTSTRAP.md).
It verifies the exact Samuel binding, essential rules and init skills; **always**
verifies the central skill catalog and capability registry; and proactively loads
`GITHUB_BRANCH_DELETE` / `repository-mutation` routing to the permanent
[Samuel branch-delete workflow](.github/workflows/samuel-branch-delete.yml).
Initialization remains **read-only**. A deletion request is a separate authorized,
exact-SHA-guarded change to
[the request manifest](.github/requests/branch-delete-request.json).
The connector's missing delete operation is not evidence that Samuel deletion is
unavailable.

## Repository status

Foundation bootstrap. The canonical engineering principles, CCG v0.1 and Python adapter
are tracked separately in [Issue #1](https://github.com/HyungseonSong-plasma/codeQA/issues/1)
and [Issue #2](https://github.com/HyungseonSong-plasma/codeQA/issues/2).

## Repository layout

The `repository_layout` policy is resolved through the
`[tool.codeqa.resources]` registry in `pyproject.toml`.
The root layout is frozen. The evaluator reads directory and file names
**only from the JSON policy**, and
`tests/test_repository_layout.py` checks the tracked repository layout.

- `.github/`: repository automation and CI
- `contracts/`: language-independent schema and interface contracts
- `docs/`: architectural decisions, principles and documentation
- `fixtures/`: fixed conformance test inputs and expected results
- `profiles/`: reusable quality profiles and codeQA's own layout policy
- `skills/`: QA skills invoked by the central OS
- `src/`: Python-first Core, adapters, evaluation, pipeline, governance and infrastructure
- `tests/`: contract, unit and integration tests

The implementation language for codeQA and adapter integration is Python-first.
An adapter may invoke external language-specific parsers; CCG contracts remain
independent of implementation languages. GitHub mutation remains owned by
`chatgpt-operation`.

## Resource location independence

Consumers reference logical IDs rather than hard-coded resource file paths:

```python
from codeqa.infrastructure.resources import ResourceRegistry
from codeqa.evaluation.layout import evaluate_layout

policy = ResourceRegistry(repository_root).load_json("repository_layout")
result = evaluate_layout(tracked_source_paths, policy)
```

Only the repository-root `pyproject.toml` is a fixed bootstrap locator.
Moving a resource changes just its `[tool.codeqa.resources]` mapping.
The resolver fails closed on missing, malformed and unsafe resources.

The separate CI frozen-policy guard compares policy contents against the Git
base commit, irrespective of their paths. See `docs/repository-structure.md`
for its enforcement boundaries and [package structure](docs/codeqa-package-architecture.md).

## Validation

```bash
python3 -m pip install -e .
python3 -m unittest discover -s tests -v
```

Git snapshot reads use `codeqa.infrastructure.git.GitReader`; pure
policy comparisons no longer invoke Git processes directly.

CCG v0.1, the conservative Python AST adapter and Mechanical QA v0.1
pipeline are implemented and tested. Full P1–P8 quality certification is not.

## CCG graph contract

The initial, language-independent CCG v0.1 exchange schema is registered as
`ccg_schema` in `[tool.codeqa.resources]` and documented in
[`contracts/ccg/README.md`](contracts/ccg/README.md).
The contract is implemented by the immutable model and validator in
`src/codeqa/core/`. The Core receives the schema as data; only the caller
resolves the logical resource ID.

```python
from codeqa.core import parse_graph, canonical_json
from codeqa.infrastructure.resources import ResourceRegistry

schema = ResourceRegistry(repository_root).load_json("ccg_schema")
graph = parse_graph(document, schema)
output = canonical_json(graph)
```

Python AST extraction is available, including conservative source-local
lexical function linking; runtime dispatch and cross-file resolution remain
unimplemented.

## Python mechanical analysis pipeline

`codeqa.pipeline.python.analyze_python` composes the syntax-only Python
Adapter, CCG Core validation and conservative mechanical review signals.
The `mechanical_profile` resource ID supplies explicit thresholds.
See [Mechanical Pipeline](docs/mechanical-pipeline.md) and
[Python Adapter](docs/python-adapter.md) for scope and limitations.

```python
from codeqa.pipeline.python import analyze_python
from codeqa.infrastructure.resources import ResourceRegistry

resources = ResourceRegistry(codeqa_repository_root)
result = analyze_python(
    {"example.py": "def hello():\n    return 1\n"},
    snapshot_id="immutable-snapshot-id",
    ccg_schema=resources.load_json("ccg_schema"),
    mechanical_profile=resources.load_json("mechanical_profile"),
)
print(result.quality.status)           # Rule-level mechanical outcome only
print(result.quality.analysis_status)  # Independent evidence limitations
print(result.quality.analysis_limitations)
```

## Reproducible QA self-audit

The [self-audit workflow](.github/workflows/self-audit.yml) executes codeQA on
its own immutable Git snapshot. A second analysis of a **fixed pre-refactor
snapshot** checks that CCG extraction and previous heuristic findings have
not silently changed with analyzer-only refactoring. Call-site observations,
resolved target identities, unresolved calls and unknown external dependencies
are reported separately. See [self-audit](docs/self-audit.md).

## Static dependency and change impact analysis

`analyze_python` now includes a separate static dependency graph.
`codeqa.evaluation.impact.analyze_change_impact` reports potential
reverse-import direct/transitive impact paths, witnesses and unknowns.
This is **observed potential static impact**, not proof of runtime coupling,
a complete impact bound or safe exclusion of tests. See [Dependency and Impact v0.1](docs/dependency-impact.md).

## Efficient evidence and incremental analysis

The Python pipeline now parses each source once per analysis, supports opt-in
content-addressed reuse, shares cross-report evidence references and provides
a unified summary. Impact traversal is optional and only reports potential
static Import paths. See [Efficient Evidence Pipeline](docs/efficient-evidence-pipeline.md).

## Contextual Call Review

Raw call-site warnings now have a non-scoring AST context overlay (call shape,
repeated callee syntax, control flow, unresolved targets). No library identity,
fluent semantics, runtime dependency or coupling score is inferred from source
syntax. The pinned [moose-test-repo audit](.github/workflows/moose-test-audit.yml)
compares the unchanged CCG/Mechanical baseline with the enriched report.
See [contextual call review](docs/contextual-call-review.md).

## Cross-module declaration evidence

The Python analysis pipeline can now report conservative cross-module
function **declaration candidates** reached by explicit unique imports,
with source and target IDs. This is not proven runtime call resolution,
does not modify CCG or v0.1 Mechanical findings, and never certifies
low coupling. See [cross-module symbol evidence](docs/cross-module-symbol-evidence.md).

## Semantic Architecture Ontology v0.1

Optional, non-scoring projection of declared directory responsibilities,
source-grounded import/CCG relationships, constraints and evidence; cannot
infer actual runtime behavior or certifiable semantic alignment. See
[Semantic Architecture Ontology](docs/semantic-architecture-ontology.md).

## Responsibility & Behavior v0.1

Optional imported-API syntax observations and evidence-backed role conflict
**review**, with no runtime side-effect inference or automatic semantic PASS.
See [Responsibility & Behavior](docs/responsibility-behavior.md).

## Language Adapter capability contract v0.1

Issue #29 defines the versioned cross-language adapter capability declaration
(`adapter_capability_schema`) and a checked Python AST support profile
(`python_adapter_capability`). See
[Language Adapter contract](docs/contracts/language-adapter-0.1.md).
This is a declaration of syntax-extraction support, never code-quality PASS.
