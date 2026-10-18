# codeQA

A language-independent, evidence-based code quality evaluation system.

## Repository status

Foundation bootstrap. The canonical engineering principles, CCG v0.1 and Python adapter
are tracked separately in [Issue #1](https://github.com/HyungseonSong-plasma/codeQA/issues/1)
and [Issue #2](https://github.com/HyungseonSong-plasma/codeQA/issues/2).

## Repository layout

The top-level layout is **frozen** by `contracts/repository-layout.json` and
`tests/test_repository_layout.py`. See `docs/repository-structure.md`.

- `.github/`: repository automation and CI
- `contracts/`: language-independent schema and interface contracts
- `docs/`: architectural decisions, principles and documentation
- `fixtures/`: fixed conformance test inputs and expected results
- `profiles/`: reusable quality profiles and templates (not consumer-owned policies)
- `skills/`: QA skills invoked by the central OS
- `src/`: Python-first Core, adapters and evaluators
- `tests/`: contract, unit and integration tests

The implementation language for codeQA and adapter integration is Python-first.
An adapter may invoke external language-specific parsers; CCG contracts remain
independent of implementation languages. GitHub mutation remains owned by
`chatgpt-operation`.

## Validation

```bash
python3 -m unittest discover -s tests -v
```

No quality result or CCG support is claimed until implemented and tested.
