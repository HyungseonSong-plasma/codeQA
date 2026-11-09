# Archived codeQA/MOOSE A/B experiments (2026-10-23)

<div align="center">
<p><strong>Completed A/B comparisons preserved as immutable historical evidence.</strong></p>
<p>23 October 2026 · Archived reports · Inert workflow snapshots</p>
</div>

---

## Experiment archive
The two experiments ran on **separate codeQA branches**. Their branch-unique
reports, measurement JSON and exact original workflow text were retained here
before the experiment refs were deleted.

- **Initial CI guard · blind vs. codeQA:** 
  [Report](moose-refactor-blind-versus-codeqa-20261023.md) ·
  [Measurements](../../.github/experiments/moose-refactor-20261023/metrics.json) ·
  [Inert workflow](../../.github/experiments/moose-refactor-20261023/workflow.yml.txt)
- **Production field · blind vs. codeQA:** 
  [Report](moose-production-field-blind-vs-codeqa-20261023.md) ·
  [Measurements](../../.github/experiments/moose-production-field-20261023/metrics.json) ·
  [Inert workflow](../../.github/experiments/moose-production-field-20261023/workflow.yml.txt)

## Evidence boundaries
> [!IMPORTANT]
> Archived workflow files are **inert `.yml.txt` documents**. Retention does
> not enable GitHub Actions on `main`, rerun numerical experiments, establish
> numerical/semantic equivalence or modify the MOOSE repository.

Exact experiment commits, frozen source scope and historical Actions-run URLs
remain recorded in the individual reports and JSON artifacts. Those recorded
commits preserve Git history even after the experiment branches are removed.

## Separate scoped pilot — schema composition (2026-11-05)

- **[Schema composition pilot v0.1 — read-only, no-go](../schema-composition-pilot-v0.1.md):**
  An evidence-scoped comparison of two JSON Schemas that did **not**
  justify deploying a new composition framework. This is a separate
  bounded experiment, **not** part of the archived October MOOSE A/B
  comparisons and **not** an adopted schema contract.

The linked pilot remains at its existing path. This index does not
relocate any document, change old URLs or anchors, or certify its
claims as independently reviewed (`NOT_EVALUATED`).
