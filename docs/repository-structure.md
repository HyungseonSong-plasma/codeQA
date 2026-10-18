# Frozen top-level repository structure (layout v1)

**Status:** Adopted / Frozen. **Owner:** codeQA Foundation, [Issue #1](https://github.com/HyungseonSong-plasma/codeQA/issues/1).

## Policy and resource resolution

The exact allowed set of top-level directories and root files is defined by
the `repository_layout` logical policy ID in
[`pyproject.toml`](../pyproject.toml) (`[tool.codeqa.resources]`).
The policy belongs to the repository's `profiles/` area, not to the public
`contracts/` interface. Consumers must retrieve it using
`ResourceRegistry(ROOT).load_json("repository_layout")`, not an embedded path.

The versioned policy is intended to remain stable while Python and other
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
| `contracts/` | Versioned, language-neutral CCG, adapter, QA report and policy **schemas** or interfaces. |
| `docs/` | Engineering principles, architecture, ADRs and usage documentation. |
| `fixtures/` | Ground-truth input/output pairs for adapters, graphs and evaluators. |
| `profiles/` | Reusable quality defaults and templates; codeQA's own repository policies. Consumer repository-specific policies remain with the consumer. |
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

1. `tests/test_repository_layout.py` resolves the policy by ID and enumerates
   **tracked** files through `git ls-files`. Its independent frozen baseline
   fails when a root file or directory is added, removed or renamed, even if
   the registry and policy file were both changed.
2. `.github/workflows/layout.yml` runs the layout and Resource Registry tests
   on pull requests and pushes to `main`, preserving the required check `layout`.
3. Moving a policy inside the approved directory boundaries requires only
   updating its `[tool.codeqa.resources]` entry; consumers retain the same ID.
   A missing or unsafe registry entry or invalid policy is a failure, not a skip.
4. A genuine top-level structural change requires a dedicated architecture issue,
   a new `docs/` ADR, a versioned policy change, matching guard-test updates
   and human approval before merge.
5. The active `codeQA-main-protection` GitHub ruleset requires PR review and
   status check `layout`, blocks force pushes/deletions and has no bypass actor.

All subdirectory design decisions remain incremental; the root structure is the
only frozen directory depth.
