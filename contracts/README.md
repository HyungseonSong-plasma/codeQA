# codeQA contracts

Versioned, language-independent exchange contracts live here:

- [`ccg/`](ccg/README.md): canonical source-code facts, graph structure,
  provenance, resolution and coverage (v0.1 initially).
- [adapters/](adapters/capability-v0.1.schema.json): language-adapter capabilities (v0.1).
- [qa/](qa/README.md): result, metric provenance, coverage and delta (v0.1).
- `profile/` (planned): schemas for valid evaluation configurations.

Contract schemas define what data **may look like**. Concrete repository
policies are stored in `profiles/` or in the consuming repository, not here.
The future contract areas are created only when their content is designed.

- [`semantic/`](semantic/README.md): Semantic Architecture Ontology v0.1 companion vocabulary and report schema; separate from frozen CCG v0.1.
