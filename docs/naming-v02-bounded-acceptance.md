# Naming Follow-up v0.2 milestone: bounded acceptance decision (Option B)

**Decision date:** 2026-10-24  
**Decision maker:** repository owner, via explicit instruction to adopt Option B  
**Status:** staged milestone acceptance; **not** evidence of external SDK/semantic/ABI/DB certification.

This change separates *what the already merged opt-in v0.2 drafts actually do*
from the longer research/production acceptance requirements. It is an explicit
acceptance-scope change, not a retroactive claim that every original checkbox
was implemented. The pre-existing ticket text remains available in GitHub
history; deferred obligations are re-recorded without omission in #91–#94.

## B-scoped v0.2 deliverables and accepted limits

| Origin | Accepted bounded v0.2 deliverable | Verification / merged evidence | Deferred full acceptance |
| --- | --- | --- | --- |
| #69 | Real pinned codeQA lexical Python declaration *candidate* inventory (26), with Git SHA and line witnesses; v0.1 unchanged | #78, #80, #81, #86 | #91: human-reviewed FP/FN inventory, policy precedence, complete declarations, Unicode, exceptions |
| #70 | Opt-in, controlled Python runtime MRO and explicit signature/callback *shape candidates*, reporting SDK/typechecker NOT_EVALUATED | #89 | #92: independently pinned SDK/stub/typechecker, actual callback binding and real compatibility |
| #71 | Opt-in, trusted synthetic Pydantic/SQLAlchemy alias and physical column witnesses; optional exact-dependency tests must be separately run | #90 | #92: external API/schema/migration compatibility, reflection/inheritance/computed fields and CI with pinned dependencies |
| #72 | Versioned *manual-curated* Rust witness profile and 15 synthetic source witnesses; trait/macro/compiler NOT_EVALUATED | #87 | #93: production Rust parser/trait/SDK evidence and real pinned language conformance |
| #73 | Compiler-backed C++ synthetic override matrix and explicit candidate MOOSE DSL namespace with `Kernels` preservation; no claimed MOOSE SDK | #88 | #93: parser-backed C++, real MOOSE grammar/SDK release and ABI/dynamic consumer evidence |
| #74 | Opt-in owner/alias/scope/expiration glossary *candidates* and seven pinned codeQA negative-control candidates, unreviewed | #85 | #91: official glossary approval and manually adjudicated negative controls |
| #75 | Existing versioned source Naming Delta comparator plus lexical false declared-rename regression guard; no semantic migration proof | #79, #83 | #94: full cross-revision equivalence/drift/rename semantics, human-reviewed mappings |
| #76 | Versioned, non-mutating rename impact *proposal* with source SHA, boundary blockers and unknowns | #84 | #94: real binding coverage and human-reviewed migration plan |

## Required acceptance invariants

1. Each v0.2 milestone module remains additive and opt-in. No frozen CCG,
   Naming v0.1, Mechanical, QA Result, or Delta contract is silently changed.
2. `NOT_EVALUATED`, `AWAITING_HUMAN_REVIEW` and `UNVERIFIED_PROPOSAL` are
   real result limitations and must not be presented as proof or score.
3. Human/domain acceptance of policy, public SDK, database schema, MOOSE DSL
   or migration behavior **is not inferred** from this scope choice.
4. A previously completed PR must have an exact-head successful repository CI
   witness. Skipped optional tests are NOT_EVALUATED, not validated.
5. Closing #69–#76 under this decision means the **revised bounded milestone**
   is accepted; the original long-horizon goals remain OPEN in #91–#94.
   Closure comments must cite this decision and the corresponding successor.
6. No automated source rename, database/API/ABI migration, fabricated human
   review, or public package publication is authorized by this document.

## Package milestone (after bounded naming acceptance)

Build and independently smoke-test a Python distribution from `src/codeqa/`
as an isolated wheel and sdist. Keep the frozen root layout and the existing
repository-root resource registry semantics. A wheel alone does **not** bundle
`profiles/` and `contracts/` by default; consumer usage requiring policy
resources must pass an explicit policy checkout/data source, and tests must
prove no hidden dependency on the source checkout. Do not publish to PyPI or
claim standalone bundled policy resources without dedicated design approval.

Package artifacts and build/install logs are separate from naming semantics.
