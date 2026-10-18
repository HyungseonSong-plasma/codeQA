# Frozen top-level repository structure (layout v1)

**Status:** Adopted / Frozen. **Owner:** codeQA Foundation, [Issue #1](https://github.com/HyungseonSong-plasma/codeQA/issues/1).

## Policy and resource resolution

The `repository_layout` logical resource ID is defined by
[`pyproject.toml`](../pyproject.toml), in the `[tool.codeqa.resources]`
registry. The current JSON document is an instance of a **repository policy**,
not a universal contract. Its physical path is intentionally replaceable.

The accepted codeQA policy describes the frozen root directory and file names.
**Only that JSON lists those names.** The evaluator and its generic tests do
not embed them.

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

## Responsibility boundaries

| Root directory | Single primary responsibility |
| --- | --- |
| `.github/` | CI/workflows and repository configuration, not GitHub mutation services. |
| `contracts/` | Versioned, language-neutral CCG, adapter, QA report and policy schemas/interfaces. |
| `docs/` | Engineering principles, architecture, ADRs and usage documentation. |
| `fixtures/` | Ground-truth adapter/graph/evaluator test datasets. |
| `profiles/` | Concrete reusable quality defaults and codeQA's own repository policy. |
| `skills/` | QA skills exposed to Samuel/David orchestration. |
| `src/` | Python-first codeQA packages, separated by [responsibility boundaries](codeqa-package-architecture.md). |
| `tests/` | Contract, behavior, regression, adversarial and integration verification. |

## Separation of verification concerns

1. **Generic layout evaluator**: `codeqa.evaluation.layout.evaluate_layout(paths, policy)`
   is a pure function that compares arbitrary repository paths with its provided
   JSON layout policy. No filesystem, GitHub, Git or codeQA folder names.
2. **Live codeQA self-check**: `tests/test_repository_layout.py` supplies the
   checked-out tracked Git paths and policy loaded via
   `ResourceRegistry(ROOT).load_json("repository_layout")`.
3. **Frozen policy guard**: `codeqa.governance.frozen_policy` compares the
   *logical policy contents* to the protected base commit. It resolves the
   baseline path from the **baseline commit's registry**, and the current path
   from the current registry. Relocation with identical contents passes.
   Moving paths and changing policy contents simultaneously fails.
4. **CI**: `.github/workflows/layout.yml` runs all unit tests and, on PR/push,
   compares with `github.event.pull_request.base.sha` or
   `github.event.before`. The job retains the branch ruleset-required
   check name `layout`. A missing baseline is a failure, not a skip.

## Protection limits and change control

- This checks accidental/ordinary edits to the frozen policy against the
  previous approved revision without embedding codeQA's directory names in
  tests. A legitimate policy change needs a dedicated architectural issue,
  an ADR, and a coordinated update to policy governance.
- **Not tamper-proof**: GitHub Actions workflows and guard code live in the
  same repository. A PR that also modifies them can potentially bypass this
  check. Hard protection of these files requires a trusted external CI check
  or a GitHub organization/repository ruleset that restricts changes to them.
  The repository currently requires PR + `layout` check, but reviews are 0.
- Only the top-level directory structure is frozen. Subdirectory design
  remains incremental, and consumer repository policies remain owned by the
  consuming repositories.

## Other non-negotiable boundaries

- CCG represents code facts; Quality Evaluation applies the eight engineering
  principles under explicit profiles.
- Native language parsers may be wrapped by Python adapters, but language-
  specific AST objects must not enter the universal CCG.
- GitHub changes remain owned by `chatgpt-operation`; codeQA consumes pinned
  source snapshots.
- `fixtures/` tests analyzer correctness; it does not establish self-audit PASS.
- `UNRESOLVED` and `NOT_EVALUATED` findings must not be reported as PASS.
