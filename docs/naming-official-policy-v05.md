# Official Naming v0.5 — adopted exact-source lexical scope (#144)

**Status: ADOPTED_SCOPED_LEXICAL_ONLY — 2026-10-26.**

The project owner explicitly approved the **precise initial scope** from
[Draft PR #150](https://github.com/HyungseonSong-plasma/codeQA/pull/150)
in the current conversation. This is the owner's *policy decision*, not
an independent reviewer signature or third-party semantic attestation.

## Effective decision

| Field | Adopted scope |
| --- | --- |
| Repository | `HyungseonSong-plasma/codeQA` |
| Language / application | Python, **explicit opt-in only** |
| Exact source snapshot | `main@1fca848833167829752b4fda8632ef06aa77dd49` |
| Exact declaration | `src/codeqa/core/complexity.py:10` — `ControlFlowObservation.node_id` |
| Python kind / evidence | class-body annotation, standard-library dataclass `FIELD_CANDIDATE` |
| Canonical spelling | `node_id` |
| Noncanonical lexical spelling | `nodeid` (lexical spelling convention only, *not* proven semantic equivalence) |
| Historical proposed `time_step` | **No adopted source scope** |
| Other `node_id` sites | **Not adopted** |
| Adoption date | **2026-10-26** |
| Owner review due | **2027-04-24**, 180 calendar days after adoption |
| Exception inventory | Empty; future exceptions need separately approved owner, reason, exact scope and expiry |
| Source rename / external contract | **Not authorized / not evaluated** |

Adopted resource: `codeqa_python_naming_scoped_v05_policy` ->
`profiles/codeqa-python-naming-scoped-v0.5.json`. It is **independent**
of the existing `python_naming_glossary_profile` v0.1 and does not
change its default behavior or any existing CCG/Mechanical/QA contracts.

The original signed-*nothing* v0.5 **proposal** remains separately
versioned and `PENDING_FINAL_OWNER_APPROVAL` as a historical candidate
artifact. The **adopted** resource is distinct and mechanically restricted
to the exact scope the user approved. The adopted JSON is not itself a
human signature or a record of external-source review.

## Machine semantics

`evaluate_pinned_official_naming_v05` verifies the original Git commit,
root tree, blob identity, source bytes and unique annotated dataclass field
using the trusted Git reader and earlier strict proposal classifier.
It then applies the owner-approved, **exact-declaration** adopted policy:

- `SCOPED_LEXICAL_CONFORMANT`: only that exact historical declaration,
  when explicitly evaluated within the approved 180-day review period;
  **not** semantic Naming PASS or global project conformance.
- `NOT_APPLICABLE`: a different path, owner, declaration, kind, line, or
  a date before adoption. No inference or fallback scope widening.
- `REVIEW_REQUIRED`: due if evaluating after **2027-04-24** without
  fresh owner reapproval; never silently renew.

Changing any approved term, alias, owner, path, scope, source evidence, dates
or exception fields without a **separately versioned owner decision**
fails the exact-profile gate. Policy output includes a deterministic
fingerprint, its original source pin, evidence scope and all explicit
limitations. No source code is rewritten.

## Explicit boundaries and future changes

This adoption governs **lexical naming convention for one pinned internal
Python field**. It **does not prove** CCG field semantic meaning, a runtime
object graph, synonym/homonym meaning, compatibility of import/reexport
users, or correctness of API/DTO/DB consumers. Automatic rename,
global QA PASS, policy gate authorization and physical-unit conclusions
remain disallowed.

Other 12 historically examined `node_id` declarations, `time_step`
applications and broader internal naming scope require new bounded,
evidence-backed decisions in [#144](https://github.com/HyungseonSong-plasma/codeQA/issues/144).
External callers remain *unavailable* and archived in
[closed, not-planned #147](https://github.com/HyungseonSong-plasma/codeQA/issues/147);
the present adoption does not reopen or silently pass that work.

Reviewing on 2027-04-24 does not automatically renew the policy. The
project owner must explicitly reapprove a new dated artifact.
