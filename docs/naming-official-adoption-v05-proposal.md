# Official Naming v0.5 — narrowly scoped adoption proposal (Issue #144)

**Status: PENDING_FINAL_OWNER_APPROVAL, not adopted.** This is a concrete
proposal for project-owner decision, not a change to default Naming v0.1
or evidence that a domain-semantic glossary has been adopted.

## Already owner-approved directions versus still pending adoption

The project owner's [policy-direction decision in #91](https://github.com/HyungseonSong-plasma/codeQA/issues/91#issuecomment-6413057026)
approved four principles: explicit canonical spellings and noncanonical
aliases; Python-only opt-in application; pinned AST declaration evidence;
and final owner authority with accountable expiring exceptions and a
180-day policy review cadence after actual adoption.

**Those principles are not themselves the final versioned policy approval.**
The final expected source scope and semantic meaning were not approved then.
This proposed version does not manufacture a human signature, adoption date
or reviewer attestation.

## Narrow initial scope offered for approval

| Dimension | Proposal |
| --- | --- |
| Repository/language | `HyungseonSong-plasma/codeQA` / Python only |
| Applicability | Explicit opt-in on a **single exact declaration**, not a path prefix |
| Source | `src/codeqa/core/complexity.py:10` pinned at `1fca848833167829752b4fda8632ef06aa77dd49` |
| Lexical owner/kind | `ControlFlowObservation.node_id` / class-body `AnnAssign`, stdlib dataclass **FIELD_CANDIDATE** |
| Proposed canonical spelling | `node_id` |
| Declared noncanonical spelling | `nodeid` (spelling direction only; no semantic equivalence inferred) |
| Role label | *Internal CCG declaration identifier candidate*, **not** verified runtime or cross-module role |
| `time_step` | Canonical spelling direction retained, **zero application scopes** and no domain meaning claim |
| External APIs, SDK, DTO/DB | Not evaluated; closed [#147](https://github.com/HyungseonSong-plasma/codeQA/issues/147) retained as reference |
| Review cadence | 180 days **only from actual later approval date** |
| Exceptions | Empty; future exceptions require independently validated owner, reason, exact scope, expiration |
| Source rename and Naming PASS | Explicitly not authorized |

The witness comes from the actual `ControlFlowObservation` declaration,
the checked-in Python complexity producer and source-bound import
investigations. This confirms an exact lexical/structural instance
for policy consideration, **not** semantic identity of all
`node_id` fields, aliases, downstream code or public consumers.
The alias `nodeid` is proposed as a noncanonical *spelling*, not
a synonym whose runtime meaning is established.

## Technical admission requirements

`profiles/codeqa-python-naming-scoped-v0.5-proposal.json` is
machine-validated by the separate, opt-in
`codeqa.pipeline.naming_official_adoption_v05.verify_pinned_naming_adoption_proposal`.
It first resolves the historical Git revision/tree and exact
`src/codeqa/core/complexity.py` blob through Git, then verifies source
SHA-1 and SHA-256, unique AST class owner/name/kind/line, `str` type and
the static stdlib dataclass `FIELD_CANDIDATE` classifier.

The result `SOURCE_EVIDENCE_READY_OWNER_DECISION_REQUIRED` cannot become
`ADOPTED`, a universal semantic PASS or a rename authorization by
altering a JSON status. Tests reject invented signatures, approval dates,
unsafe scope widening, false synonym equivalence and stale source.

The proposal intentionally leaves `adoption_date=null` and
`next_review_date=null`; these must be set **only after** a separate
explicit project-owner decision on the final term/scope and a
versioned adoption change. The existing v0.3 owner proposal and
v0.4 glossary candidate stay `NOT_ADOPTED`; no policy fingerprint
or default QA contract is replaced.

## Owner decision required

The reviewer needs to decide whether the above **single declaration**
is an acceptable initial official internal Naming scope, without
extending it to the other 12 historical `node_id` candidates or
to `time_step`, `nodeid` aliases or external consumers.

Until a separately approved adoption commit exists, **official adoption
remains pending**. Further expansion is a distinct scoped review with
real source and meaning evidence. Issue #144 stays Open.
