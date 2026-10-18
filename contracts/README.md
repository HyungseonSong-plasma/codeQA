# codeQA contracts

Versioned, language-independent exchange contracts live here:

- [`ccg/`](ccg/README.md): canonical source-code facts, graph structure,
  provenance, resolution and coverage (v0.1 initially).
- `adapter/` (planned): language-adapter input/output and capability reporting.
- `quality/` (planned): findings, evidence, coverage and verdicts.
- `profile/` (planned): schemas for valid evaluation configurations.

Contract schemas define what data **may look like**. Concrete repository
policies are stored in `profiles/` or in the consuming repository, not here.
The future contract areas are created only when their content is designed.
