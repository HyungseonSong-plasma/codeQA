# codeQA Python package structure

**Status:** Adopted. This fixes the first-level responsibilities inside `src/codeqa/`,
without prematurely designing implementation subpackages.

```text
src/
└── codeqa/
    ├── __init__.py
    ├── core/
    │   ├── graph.py
    │   └── validation.py
    ├── adapters/
    │   └── python.py
    ├── evaluation/
    │   ├── layout.py
    │   └── mechanical.py
    ├── pipeline/
    │   └── python.py
    ├── governance/
    │   └── frozen_policy.py
    └── infrastructure/
        └── resources.py
```

| Package | Primary responsibility |
| --- | --- |
| `core/` | Language-neutral CCG domain model and invariants. |
| `adapters/` | Language-specific code interpretation and CCG conversion. |
| `evaluation/` | Pure quality measurement, evidence-based analysis and verdicts. |
| `pipeline/` | Compose internal analysis stages; not GitHub mutation or Samuel/David orchestration. |
| `governance/` | Frozen-policy and repository integrity checks. |
| `infrastructure/` | Resource Registry, filesystem, settings and technical integration. |

## Dependency boundaries

- `core` does not import any outer package, including `adapters`, `evaluation`, or `infrastructure`.
- `adapters` can use `core`; `evaluation` can use `core`, but must not use adapter-specific ASTs.
- `pipeline` composes adapters, evaluation and infrastructure behind defined interfaces.
- `governance` may use `infrastructure` to resolve policy resources.
- `infrastructure` must not depend on the CCG domain, adapters, evaluation, pipeline or governance.
- Policy file locations belong only to the `[tool.codeqa.resources]` registry.
  Directory names allowed at repository root belong only to the JSON policy.

## Migration and verification

The preexisting root-level Resource Registry now lives in `infrastructure/`,
and the preexisting frozen-policy guard now lives in `governance/`.
Imports in unit tests and the mandatory CI `layout` step use the new module names.
This is a pre-public-API internal refactor; compatibility aliases are not added.

`core/` implements CCG v0.1 validation; `adapters/python.py` extracts
conservative syntax facts; `evaluation/mechanical.py` measures only explicit
review heuristics; `pipeline/python.py` composes them without filesystem,
GitHub or external OS orchestration.

The frozen top-level repository structure and its JSON layout policy stay unchanged.

## Refactoring boundary

`infrastructure.git.GitReader` is the sole production subprocess adapter for
local Git snapshot inspection. It is **read only** and does not replace
`chatgpt-operation` ownership of GitHub operations. Governance consumes this
infrastructure API and compares loaded policy values in a pure function.

`resources.parse_registry` and `resources.parse_json` normalize interpretation
of current working-tree bytes and historical Git blobs. No new infrastructure
layers were introduced beyond the single reusable Git reader.

A proper setuptools `src` package is now defined in `pyproject.toml`. Run
`python3 -m pip install -e .` before testing. Individual tests must not modify
`sys.path` to locate implementation modules.

The Core receives JSON Schema from its caller (e.g. through the outer Resource
Registry); it never imports infrastructure or holds physical contract paths.

Thresholds belong to the `mechanical_profile` logical resource in
`profiles/`. Quality verdicts are currently internal report objects, not
yet a stable, external Quality Contract.
