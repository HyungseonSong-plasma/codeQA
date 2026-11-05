# Architecture QA B8 v0.1 — unprompted codeQA self-diagnostic

Run `python .github/scripts/architecture_self_diagnostic_e2e.py --output-dir architecture-e2e`
from a clean, installed checkout. The runner binds every B1–B7 stage to
`git rev-parse HEAD`, checks `EXPECTED_HEAD` when provided, and never accepts
a Naming/Adapter question or a target package name as input.

It invokes the existing B1 inventory, B2 dependency metrics, B3 opportunity
discovery, B6 language-family boundaries, B4 virtual scenarios, B5 static
migration-impact analysis and B7 conservative assessment. B7 schema validation
and exact-source hashes are retained; B8 independently binds each signal and
question witness to a read B1 source blob, rejects orphan/duplicate questions,
and checks that KEEP and unresolved consumer caveats survive projection.

Artifacts:

- `architecture-signals.json`: source identity, coverage, measured signal
  witnesses and limitations.
- `question-opportunities.json`: only independently triggered opportunities;
  an empty list is valid and is never reported as quality PASS.
- `architecture-assessment.json`: the original B7 assessment, including
  rejected virtual scenarios and bounded Pareto decisions.
- `architecture-self-diagnostic.md`: source lines, metric trigger,
  counterhypothesis, KEEP, migration/consumer unknowns and dispositions.

All JSON uses a deterministic ordering and the two projections validate against
`contracts/qa/architecture-self-diagnostic-v0.1.schema.json`. The workflow
uploads all four as a single exact-head artifact. CI runs renamed-package,
independent concentration/cycle, no-signal, misleading-name and forged-witness
regressions without introducing hardcoded architecture questions.

**Limits:** B8 discovers *potential* architecture questions, not a proof that
any module should move. Dynamic imports, external callers, semantic ownership,
runtime behavior, public API compatibility and unsupported language coverage
remain unverified. A healthy no-signal repository may legitimately produce
zero questions. No source migration occurs. A later actual cleanup requires a
separately reviewed PR, compatible tests and a same-policy/scope rerun comparing
before and after evidence. If no safe virtual candidate exists, do not invent
one or call the resulting recommendation PASS.

## Rejected candidate provenance (#184)

B4 `TARGET_COLLISION` rejections now preserve exact source/destination paths,
source SHA-256 and any existing target SHA-256. The B8 human report renders
those witnesses. This improves reproducibility of the *rejection*; it does not
turn a rejected move into a viable candidate or authorize any source migration.


## Real codeQA close-first assessment ledger (#184 / #166)

The exact-source original and subsequent B8 artifacts were independently
compared in [the 43-edge evidence ledger](architecture-qa-184-close-first-evidence.md).
It records all witnessed Pipeline source/target pairs and the measured B4
occupied-destination and forbidden-direction rejections, while preserving
`SEMANTIC_RESPONSIBILITY_NOT_EVALUATED` and external-consumer limitations.
An observed cross-role ratio must not prompt a forced package move when all
measured imports follow the documented composition direction and no independently
supported, noncolliding migration has survived review. `NO_MOVE` is an action
under insufficient evidence, not an architecture quality PASS.

The B8 workflow still derives its question(s) from actual source evidence,
not these written findings. Any subsequent source change requires a fresh
matched-scope B1–B8 comparison, test and API assessment and separate approval.
