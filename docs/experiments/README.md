<div align="center">
<h1>Archived codeQA / MOOSE Experiments</h1>
<p><strong>Completed A/B comparisons preserved as immutable historical evidence.</strong></p>
<p>23 October 2026 · Archived reports · Inert workflow snapshots</p>
</div>

---

## Experiment archive

The two experiments ran on **separate codeQA branches**. Their branch-unique
reports, measurement JSON and exact original workflow text were retained here
before the experiment refs were deleted.

| Comparison | Report | Measurements | Original workflow (inert text) |
| :-- | :-- | :-- | :-- |
| Initial CI guard · blind vs. codeQA | [Initial CI guard comparison](moose-refactor-blind-versus-codeqa-20261023.md) | [Measurement JSON](../../.github/experiments/moose-refactor-20261023/metrics.json) | [Archived workflow](../../.github/experiments/moose-refactor-20261023/workflow.yml.txt) |
| Production field · blind vs. codeQA | [Production field comparison](moose-production-field-blind-vs-codeqa-20261023.md) | [Measurement JSON](../../.github/experiments/moose-production-field-20261023/metrics.json) | [Archived workflow](../../.github/experiments/moose-production-field-20261023/workflow.yml.txt) |

## Evidence boundaries

> [!IMPORTANT]
> Archived workflow files are **inert `.yml.txt` documents**. Retention does
> not enable GitHub Actions on `main`, rerun numerical experiments, establish
> numerical/semantic equivalence or modify the MOOSE repository.

Exact experiment commits, frozen source scope and historical Actions-run URLs
remain recorded in the individual reports and JSON artifacts. Those recorded
commits preserve Git history even after the experiment branches are removed.
