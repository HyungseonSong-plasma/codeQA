# Architecture concentration policy triage v0.1

This is an evidence-gathering slice of #184, derived from Architecture QA parent #166. It does **not** authorize a package move or close the product-outcome gate.

`codeqa.evaluation.architecture.policy_triage.triage_cross_role_concentration` consumes the exact B1 inventory, B2 static import metrics, B3 opportunity report and the same declared role policy. It verifies the source SHA, policy digest, report IDs, measured denominator, observed witnesses and per-signal source role before classifying the observed cross-role import pairs.

For each `CROSS_BOUNDARY_CONCENTRATION` signal, it returns every observed pair with path, line, source SHA-256 and one **declared direction** status:

- `DECLARED_ALLOWED`: the role policy does not prohibit the target role.
- `DECLARED_FORBIDDEN`: the direction contradicts the declared policy.
- `DECLARED_TRANSITIONAL_REVIEW`: a documented exception applies to a normally forbidden direction.

All three statuses leave `semantic_ownership=NOT_EVALUATED` and `external_consumers=NOT_EVALUATED`. In particular, `DECLARED_ALLOWED` means neither that the imported behavior belongs in the current module nor that moving it would be safe. The triage result always has `decision=NOT_EVALUATED`; it does not return `KEEP` or `PREFER`. A healthy/no-concentration result is an empty list, not a PASS.

The B8 real-repository self-diagnostic now appends the triage census to its existing Markdown evidence artifact. It does not seed questions with Naming, Adapter, or pipeline labels, and it does not mutate source. Its measured counts are tied to the current exact HEAD and can change with the repository.

## Current #184 baseline

At PR #185 HEAD `f3b5379d0a716a000f9ec5c3b405e1d287b12ebf`, B8 artifact `12798617728` records **43 cross-role / 48 outgoing pipeline pairs**. All 43 directions are permitted by `profiles/semantic-directory-roles-v0.1.json`, which explicitly describes `pipeline` as composing adapters, core and evaluators. This is **support for the benign orchestration counterhypothesis**, not proof that each pair is correctly owned.

The automatic virtual move `src/codeqa/pipeline/python.py -> src/codeqa/adapters/python.py` remains rejected as `TARGET_COLLISION` because the destination is occupied. PR #185 preserves exact hashes for that rejection; this triage does not rename the destination or create a new candidate.

## Remaining acceptance gates

Review actual source behavior and tests for ownership leakage, inventory known package and public import consumers, and compare KEEP only against independently supported noncolliding alternatives using matched B1/B2/B3/B5/B7 evidence. Unknown external consumers and API compatibility must remain `NOT_EVALUATED`. Any justified actual move requires its own policy/public-API approval, a separate PR and exact-head CI followed by same-scope re-audit. Parent #166 remains open until its product outcome is independently verified.

## Same-source candidate disposition (follow-up #184)

The B8 runner now appends a deterministic concentration-candidate section
using `render_policy_candidate_decisions`. It binds the policy triage's
source/profile/inventory/metrics/opportunity identity to the B7 assessment ID
and refuses mismatched or tampered reports. Each measured concentration signal
is associated with its originating B7 question, the accepted B4/B5 scenario
comparisons (including the actual B7 verdict, matched denominators, migration
risk and unresolved consumers), and the rejected B4 mappings.

A `TARGET_COLLISION` with exact path/hash witnesses yields **KEEP for that
specific rejected mapping only**. It does **not** produce a repository-wide
KEEP, PASS, or proof of semantic cohesion. If no viable alternative exists,
the current no-move action is conservative, not a quality verdict. A valid
noncolliding candidate retains B7's actual comparison verdict and unknowns.
All external-consumer and semantic-ownership claims remain `NOT_EVALUATED`.
No automatic source migration is added. Tests cover occupied destinations,
noncolliding comparisons, healthy zero-signal input, stale SHA, and forged
report digests.

The real codeQA pipeline imports are permitted composition *directions*
under the declared role policy; that is a useful benign counterhypothesis,
not proof that every import is semantically correct. The separately merged
GitReader centralization (#188) is the actual supported ownership cleanup.
It must not be conflated with an unsupported pipeline-to-adapter relocation.
