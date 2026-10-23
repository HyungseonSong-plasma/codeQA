# Archived codeQA/MOOSE A/B experiments (2026-10-23)

The two completed experiments were developed on separate `codeQA` branches.
The branch-unique report, measurement JSON, and exact original workflow bytes
were preserved here before deletion of those experiment refs.

- [Initial CI guard comparison](moose-refactor-blind-versus-codeqa-20261023.md)
  and [measurements](../../.github/experiments/moose-refactor-20261023/metrics.json).
  Original executable workflow is archived *inertly* as
  `.github/experiments/moose-refactor-20261023/workflow.yml.txt`.
- [Production field comparison](moose-production-field-blind-vs-codeqa-20261023.md)
  and [measurements](../../.github/experiments/moose-production-field-20261023/metrics.json).
  Original executable workflow is archived *inertly* as
  `.github/experiments/moose-production-field-20261023/workflow.yml.txt`.

Archiving workflow text does **not** enable Actions on `main`, rerun
numerical experiments, prove equivalence, or change the MOOSE repository.
Exact experiment commit SHA, frozen source scope and historical Actions run
URLs remain in the corresponding reports and JSON files. The immutable Git
history remains accessible after branch removal through recorded commits.
