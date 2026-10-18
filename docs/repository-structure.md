# Frozen top-level repository structure (layout v1)

**Status:** Adopted / Frozen. **Owner:** codeQA Foundation, [Issue #1](https://github.com/HyungseonSong-plasma/codeQA/issues/1).

## Contract

The complete allowed set of top-level directories and root files is defined in
[`contracts/repository-layout.json`](../contracts/repository-layout.json).
The versioned contract is intended to remain stable while Python and other
language-specific analyses, CCG, rules and skills evolve *inside* these boundaries.

```text
codeQA/
├── .github/
├── contracts/
├── docs/
├── fixtures/
├── profiles/
├── skills/
├── src/
├── tests/
├── .gitignore
├── README.md
└── pyproject.toml
```

## Ownership

| Root directory | Single primary responsibility |
| --- | --- |
| `.github/` | GitHub CI/workflows and repository automation configuration only. GitHub operation APIs/skills belong to `chatgpt-operation`. |
| `contracts/` | Versioned, language-neutral CCG, adapter, QA report, and layout contracts. |
| `docs/` | Engineering principles, architecture, ADRs and usage documentation. |
| `fixtures/` | Ground-truth input/output pairs for adapters, graphs and evaluators. |
| `profiles/` | Reusable quality defaults and templates. Consumer repository-specific policies remain with the consumer. |
| `skills/` | QA capabilities exposed to the external Samuel/David orchestrator. |
| `src/` | Python-first codeQA Core, adapters and evaluators, separated by internal module boundaries. |
| `tests/` | Contract, behavior, regression, adversarial and integration verification. |

## Non-negotiable architectural boundaries

- CCG describes source-code facts; Quality Evaluation applies the eight universal
  principles; repository policy belongs in explicit quality profiles.
- `src/` may contain adapter integrations written in Python, including Python
  wrappers for external native-language parsers; language-specific AST objects must
  not enter the canonical CCG contract or general-purpose evaluators.
- All GitHub repository mutation/PR/workflow operations remain in `chatgpt-operation`;
  `codeQA` consumes immutable repository snapshots.
- `fixtures/` validates analyzer behavior; self-audit independently evaluates
  actual `codeQA` sources. Fixture success does not establish self-audit PASS.
- An `UNRESOLVED` or `NOT_EVALUATED` finding must never be reported as PASS.

## Enforcement and change control

1. `tests/test_repository_layout.py` reads the contract and enumerates **tracked**
   files through `git ls-files`; its test fails when any root file or directory
   is added, removed or renamed, or when the manifest alone is loosened.
2. `.github/workflows/layout.yml` runs the check on pull requests and pushes
   to `main`. This provides a reproducible repository CI gate.
3. A genuinely necessary top-level structural change requires a dedicated
   architecture issue, rationale in a new `docs/` ADR, a versioned layout
   contract change, matching guard-test updates, and human approval before merge.
4. To prevent bypassing the CI gate, configure GitHub `main` branch protection
   or an organization ruleset to **require** `Repository Layout Guard / layout`
   checks and approved PR reviews. Until that GitHub setting is active, this
   guard is a detectable policy, **not** an unbypassable lock.

All subdirectory design decisions remain incremental; the root structure is the
only frozen directory depth.
