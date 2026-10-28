# Architecture Assessment B7 v0.1 — source evidence before questions

The opt-in evaluator in `codeqa.evaluation.architecture.assessment` consumes
B1 inventory, B2 dependency metrics, B3 unprompted opportunity discovery,
B4 virtual path scenarios, B5 migration impact and optional B6 declared
language-family boundary evidence from the **same exact source snapshot**. It does not invoke an LLM, edit source or assume Naming/Adapter
should be split. The normal entrypoint has no question input and can return
zero signals, zero opportunities and zero assessments.

## Evidence and decision boundaries

The versioned JSON report `contracts/qa/architecture-assessment-v0.1.schema.json`
contains immutable source identity, B1–B5 analyzer/report hashes, inventory
coverage, measured architecture signals, source-backed question opportunities,
optional scenario assessments, rejected candidates, unknowns, provenance and
an empty reviewer-decision section. Each question carries its originating signal
IDs, source witnesses, benign counterhypothesis and evidence limitations.
ChatGPT may rephrase an observed opportunity as a question, but its words are
an inference, never an observed source fact. The separate
`assess_explicit_question` entrypoint is labeled `EXPLICIT_QUESTION` and
cannot claim discovery recall.

The deterministic `compare_bounded_layouts` contract requires the same
source, inventory, metrics, role policy, profile and denominator identities.
Five lower-is-better proxy objectives are compared without weights:
cross-boundary static pairs, static cycles, reverse-import change surface,
added interface burden and migration reference sites. These are *not*
semantic cohesion, runtime behavior or observed maintainability.

1. Missing/inconsistent identities, denominators or metrics yield
   `INSUFFICIENT_EVIDENCE`.
2. Known hard constraint violations or namespace collisions yield `KEEP`.
   Unknown critical external callers, packaging or public API compatibility
   yield `INSUFFICIENT_EVIDENCE`, never a fabricated zero-risk score.
3. Path-only moves cannot count an improved role-label proxy as physical
   graph improvement. Added migration burden favors `KEEP`; unresolved
   ownership and conflicting objectives require `REVIEW_REQUIRED`.
4. A candidate can receive provisional `PREFER` only when independently
   verified relationship changes make it no worse on all comparable objectives,
   materially better on at least one, and no critical risk remains.
5. An advisory result is never permission to refactor. Real migration requires
   a separately authorized PR, exact-head CI and same-policy/scope
   post-change comparison including API and packaging tests.

`OBSERVED`, `DECLARED_POLICY`, `PROXY_INFERENCE` and `HUMAN_REVIEW`
are kept separate. Static import witnesses, a green CI run, and absence of
observed cycles do not establish semantic safety. Dynamic imports, external
consumers, Rust/C++ macro/trait/ABI semantics and production runtime remain
`NOT_EVALUATED` without independent evidence.

## Reproducibility

`python -m unittest discover -s tests -p 'test_architecture_assessment_v01.py' -v`
covers favorable/dominated/tied/conflicting/unknown candidates, hard
constraints, tiny improvements, deceptive path-only gains, source/profile
mismatch, no-question fixtures, orphan signals and explicit-request isolation.

The exact-head workflow `.github/workflows/architecture-assessment.yml`
recomputes B1–B5 from checked-out source and runs
`.github/scripts/architecture_assessment_audit.py`. It validates the JSON
Schema, emits `architecture-assessment.json` and an accompanying
`architecture-assessment.md` from the same evidence object, and uploads both.
These artifacts are source-bounded advisory evidence, not an approved
architecture plan or post-migration proof.

## Next stage

B8 #174 must run this full chain against codeQA and independent fixtures,
report actual unprompted findings and limits, and demonstrate a separately
authorized cleanup and same-scope post-change re-diagnosis where safe and
supported. If no safe move is supported, do not invent one to satisfy a
demonstration.

## B8 follow-up: declared package exposure (#184)

The opt-in B8 workflow also emits `architecture-package-surface.json` from
one exact-HEAD B1 inventory, the B3-derived internal-consumer census and the
tracked `pyproject.toml` bytes. It validates the configuration file SHA-256
against the inventory and records potential Python import names, observed
static importers and setuptools package-discovery declarations. A module is
only a `DECLARED_DISCOVERY_CANDIDATE` when the source scope matches the
setuptools find declaration and its regular package initializer paths are
observed. The declaration is **not** evidence of a built wheel, supported
public API, executed behavioral tests, dynamic import compatibility or
external callers. Those remain `NOT_EVALUATED`; no package migration or
architecture PASS is authorized. Healthy/no-signal repositories produce an
empty module census rather than seeded package questions.
