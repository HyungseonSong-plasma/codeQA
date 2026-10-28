# Architecture QA B3 — evidence-first question opportunity miner v0.1

**Status:** opt-in implementation, source-only; no automatic recommendation, code relocation or semantic quality certification. **Issue:** #169; depends on merged B1 #167 and B2 #168.

## Contract

`codeqa.evaluation.architecture.opportunities.discover_architecture_opportunities(inventory, metrics)` accepts the B1 and B2 immutable reports from the **same exact commit and role-policy digest**. It verifies both report content digests, pair denominators and the source SHA/line identity of each observed import witness. This is a pure evaluator; the caller is responsible for attesting B1 source bytes and B2 parser correctness. Schema: `contracts/qa/architecture-opportunities-v0.1.schema.json`.

No prompt or package name is an input. In particular, the code does not match any named feature or prescribe any question. Path/role labels are used to describe **observed boundaries**, not to infer responsibilities from spelling.

## Generic, bounded triggers

| Signal | Derivation | Counterhypothesis |
| --- | --- | --- |
| `STATIC_IMPORT_CYCLE` | B2 closed SCC walk with actual import-site witnesses; count 1 / number of analyzed modules | Deferred or intentionally co-owned imports may be harmless |
| `DECLARED_BOUNDARY_CONFLICT` | A B2 forbidden declared-role edge, bound to a specific resolved pair | The policy itself may need a reviewed exception or change |
| `CROSS_BOUNDARY_CONCENTRATION` | At least three distinct cross-role directed pairs from one role, spanning at least two other declared roles, and at least 60% of that role's observed outgoing pairs | An intentional composition layer or shared utility can legitimately connect roles |

The concentration thresholds are **review triggers only**, not universal measures of good architecture. Denominators use resolved directed pairs, not statement counts or runtime calls. Missing denominators, import witnesses, mismatched source identity or tampered report hashes fail closed. No static signal alone certifies a defect.

## Output and limitations

Each `architecture_signal` includes a stable source-derived ID, family, scope roles, numerator/denominator/ratio, derivation rule, source-path/line/hash witnesses, a hypothesis, a plausible benign counterhypothesis, and explicit unknowns. Each `question_opportunity` references its originating signal ID, repeats the source evidence, provides KEEP and an investigation direction, and has `decision=NOT_EVALUATED`. ChatGPT may use this evidence to *discover/rephrase* the question. It is not an instruction to migrate.

An empty signal/opportunity list is valid (`NO_SIGNALS_OBSERVED`), but is **not** architecture PASS. External callers, dynamic imports, semantic responsibility, and non-Python parser coverage remain unverified. B2 `INCOMPLETE` stays B3 `INCOMPLETE`; missing evidence cannot become an absence-of-problems claim.

## Scope of v0.1

Tests cover zero-signal healthy graphs, static cycles, declared violations, cross-boundary concentration, intentional shared utilities, deceptive filename matches, renamed-isomorphic graphs, dynamic/partial coverage, tampered evidence and exact checked-out codeQA source. The original owner topics are withheld as regression examples, not forced outputs. Signals requiring semantic responsibility scatter, historical co-change or external consumers are **NOT_EVALUATED** until independent evidence exists.

B4 #170 may use these observed signal references to propose *virtual* layout alternatives, always including KEEP. B7 #173 must evaluate alternatives separately under hard constraints and conservative Pareto-style comparisons. B8 #174 owns full self-diagnostic and comparative report.
