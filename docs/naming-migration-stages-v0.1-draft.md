# Naming migration stage review v0.1 draft (#94, C4)

**Authority:** proposal-only, opt-in, read-only. This extends the existing
`prepare_migration_review_packet` output with a concrete rollback action and
an unverified entry/rollback-evidence status for **each** named rollout stage.
It never changes code, databases, schema, API or deployments.

## Scope

`codeqa.evaluation.naming_migration_stages.prepare_staged_migration_draft`
accepts a previously prepared `MigrationReviewPacket`, a stage-by-stage
`entry_gates`, `stage_rollbacks`, and `rollback_evidence` map.
Every map must cover exactly the stages declared in the original packet.
Rollback actions must be drawn from the packet's original rollback plan.
Duplicate stages, missing rollback paths, fabricated `PASS`, `APPROVED`,
`ALLOW`, and any source packet claiming mutation or final approval fail closed.

The returned `StagedMigrationDraft` always has:
- `status=HUMAN_REVIEW_REQUIRED`;
- `mutation_performed=false`;
- every API/SDK/DTO/DB/ABI/MOOSE boundary still listed as unverified;
- explicit unknowns for executable rollback validation, the approval of
  a compatibility window, independent stage approval, and caller-supplied
  source/proposal provenance.

## Review sequence (draft, not an execution plan)

1. Pin both distinct source revisions and profile/source-selection evidence.
2. Prepare a source-only migration review packet without claiming a rename.
3. For every proposed stage, declare its entry gate and the exact rollback
   action; keep each status `NOT_EVALUATED` or `REVIEW_REQUIRED`.
4. Review selected source and policy drift, unresolved imports/aliases,
   public interface obligations, migration impact, and rollback evidence.
5. Require **separate** independently verified consumers, final migration
   acceptance and source-change authorization before any actual rename.

These steps neither prove rollback executability nor approve a production
compatibility window. Missing external clients, Rust trait resolution, C++
ABI or MOOSE HIT DSL evidence remains `UNKNOWN`/`NOT_EVALUATED`; no
automatic source change or #94 closure is authorized.

## Regression coverage

`tests/test_naming_migration_stages.py` checks exact per-stage mappings,
malformed or duplicate stages, an unlisted rollback, forged entry/rollback
approval, forged source-packet approval or mutation, and missing/promoted
external boundary claims. Source identity attestation is **not** upgraded;
the existing #94 input migration packet remains caller-supplied.
