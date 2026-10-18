# codeQA Python package structure

**Status:** Adopted. This fixes the first-level responsibilities inside `src/codeqa/`,
without prematurely designing implementation subpackages.

```text
src/
└── codeqa/
    ├── __init__.py
    ├── core/
    ├── adapters/
    ├── evaluation/
    │   └── layout.py
    ├── pipeline/
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

`core/`, `adapters/`, and `pipeline/` currently contain package markers but
no analysis implementations. Only package boundaries are established.

The frozen top-level repository structure and its JSON layout policy stay unchanged.
