# codeQA

A language-independent, evidence-based code quality evaluation system.

## Repository status

Foundation bootstrap. The canonical engineering principles, CCG v0.1 and Python adapter
are tracked separately in [Issue #1](https://github.com/HyungseonSong-plasma/codeQA/issues/1)
and [Issue #2](https://github.com/HyungseonSong-plasma/codeQA/issues/2).

## Repository layout

The top-level layout is **frozen** by the `repository_layout` policy resolved through
the `[tool.codeqa.resources]` registry in `pyproject.toml`. Its guard is
`tests/test_repository_layout.py`. See `docs/repository-structure.md`.

- `.github/`: repository automation and CI
- `contracts/`: language-independent schema and interface contracts
- `docs/`: architectural decisions, principles and documentation
- `fixtures/`: fixed conformance test inputs and expected results
- `profiles/`: reusable quality profiles and templates; codeQA's own layout policy
- `skills/`: QA skills invoked by the central OS
- `src/`: Python-first Core, adapters and evaluators
- `tests/`: contract, unit and integration tests

The implementation language for codeQA and adapter integration is Python-first.
An adapter may invoke external language-specific parsers; CCG contracts remain
independent of implementation languages. GitHub mutation remains owned by
`chatgpt-operation`.

## Resource location independence

Consumers use logical IDs rather than hard-coded resource file paths:

```python
from codeqa.resources import ResourceRegistry

registry = ResourceRegistry(repository_root)
policy = registry.load_json("repository_layout")
```

Only `pyproject.toml` at the repository root is the fixed bootstrap locator.
Move a resource by updating its mapping in `[tool.codeqa.resources]`.
The resolver rejects missing resources, unsafe paths and broken JSON.

## Validation

```bash
python3 -m unittest discover -s tests -v
```

No quality result or CCG support is claimed until implemented and tested.
