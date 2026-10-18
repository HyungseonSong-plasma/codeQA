# codeQA

A language-independent, evidence-based code quality evaluation system.

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
python3 -m pip install -e '.[test]'
python3 -m unittest discover -s tests -v
```

Git snapshot reads use `codeqa.infrastructure.git.GitReader`; pure
policy comparisons no longer invoke Git processes directly.

No quality result or CCG support is claimed until implemented and tested.

## CCG graph contract

The initial, language-independent CCG v0.1 exchange schema is registered as
`ccg_schema` in `[tool.codeqa.resources]` and documented in
[`contracts/ccg/README.md`](contracts/ccg/README.md).
This is a data contract, not an implemented CCG engine or language adapter.
Schema conformance tests use the optional `test` extra shown above.
