# Documentation reference audit v0.1 — issue #288

**Scope:** read-only, repository-wide tracked-file audit accompanying PR
[#289](https://github.com/HyungseonSong-plasma/codeQA/pull/289).
**First measured audit HEAD:** `087cb39202a1eeb6bc31c8a6f645b83e88da3e81`
(2026-11-05, Layout workflow log). Later corrective commits repair findings;
the same [executable audit](../../tests/test_documentation_reference_audit.py)
runs on every subsequent exact PR HEAD.

## Measured baseline of the executable audit

| Metric | First audit result |
| :-- | --: |
| Git-tracked files accessible in test checkout | 609 |
| Tracked Markdown files audited (all repository directories) | 116 |
| Parsed Markdown/HTML/reference hyperlink occurrences | 459 |
| External or mail links, **not** verified over network | 78 |
| Local link occurrences | 381 |
| In-repository Markdown fragment links checked | 1 |
| Distinct resolved inbound local targets | 166 |
| Documentation files with at least one discovered inbound local link | 81 |
| **Broken local links before repair** | **2** |
| Literal `docs/*.md` / `docs/*.json` references found in tracked text | 329 |
| Distinct candidate literal `docs/` paths | 120 |
| Nonexistent-in-codeQA literal occurrences | 12 across 6 distinct path values |

The scan uses Git-tracked files rather than the working-tree filesystem
inventory. It excludes Markdown code fences and inline code from hyperlink
interpretation. Markdown headings (including duplicate-slug numbering),
reference-style links, images, ordinary inline links and simple HTML
`href`/`src` are included. It then scans tracked readable source, JSON,
YAML, TOML, Markdown, text and shell files for concrete `docs/` path
strings. It **does not** claim full CommonMark parser equivalence, public
URL availability, GitHub UI rendering, or a network crawl of unknown
external backlinks. Later counts will change as more documentation is added;
do **not** lock the numeric denominator in tests.

## Two actual broken local links corrected

Both errors were present in the previously committed
[extraction-aware P3 document](../extraction-aware-p3.md).

| Source | Before (incorrect relative target) | After (verified repository-relative target) |
| :-- | :-- | :-- |
| `docs/extraction-aware-p3.md:31` | `../../fixtures/moose-p3-refactor/provenance.json` | `../fixtures/moose-p3-refactor/provenance.json` |
| `docs/extraction-aware-p3.md:32` | `../experiments/moose-production-field-blind-vs-codeqa-20261023.md` | `experiments/moose-production-field-blind-vs-codeqa-20261023.md` |

The fix changes **link destinations only**, not measured P3 numbers, the
frozen comparison or its evidence. The exact-head CI audit is required to
show **zero broken local references after these repairs**. The initial
audit failure is retained in GitHub Actions evidence, not hidden by a
waiver or skipped test.

## Twelve nonexistent local literal occurrences — scoped disposition

These are **text strings** that do not exist in this codeQA checkout, not
necessarily broken local Markdown hyperlinks. The audit fails closed if a
*new, unreviewed path value* is introduced.

| Path string | Evidence and interpretation |
| :-- | :-- |
| `docs/contracts/ccg-0.1.md` | **Intentionally absent historical proposal.** [ADR 0001](../adr/0001-contract-authority-and-versioning.md) explicitly selects [`contracts/ccg/`](../../contracts/ccg/README.md) as the sole v0.1 authority, and tests assert the old path must not reappear. Do not create a duplicate schema explanation to silence the check |
| `docs/operating_system/ESSENTIAL_RULES.md` | **External Samuel source path.** `docs/operating_system/central_skills.json` names `HyungseonSong-plasma/chatgpt-operation` and immutable revision `c803cd6b77c6d112df33d8679bac32f993a658b0`. The path exists there with exact Git blob `9d11cb64007964a6c1fdea91779a3b25618a5098`, not in codeQA |
| `docs/architecture/physics_directory_roles_v1.json` | **External pinned MOOSE policy path**, declared by two retrospective profiles at MOOSE revision `2e14935e9bab03e684c4e01a35840d8e125802d9`; confirmed there with Git blob `01ec23633e103dc861c7ca81d498b2ce45b8e089`. Do not invent the file in codeQA |
| `docs/samuel-native-pr-e2e-fixture.md` | **Reserved, not materialized fixture path** for `samuel-native-pr-create-e2e-v1.json`, explicitly `enabled=false`. Its existence must not be implied as a completed cross-repository write |
| `docs/example.md` | **Synthetic migration test input**, not a committed documentation page |
| `docs/trailing./report.json` | **Invalid-path negative test fixture** deliberately used by the root support-surface security test |

Tests pin these exception **path values and their relevant local trust
boundaries**; the original audit records locations and occurrence counts
so future reviewers can determine whether a new occurrence is legitimate.
These six exceptions are not a blanket permit for new undocumented
nonexistent paths.

## Corrected temporal claims (without rewriting source evidence)

The following received explicit 2026-11-05 reader updates, preserving
historical original text or labeling it as historical:

1. [Architecture B1–B8 design](../architecture-assessment-design-v0.1.md):
   #165 closed/completed, but historical design approval is not equivalent
   to an independently verified layout migration.
2. [Naming v0.2 coverage](../naming-coverage-v02.md): the original slice
   did not by itself close #69; #69 later closed/completed.
3. [Contract taxonomy](../contract-taxonomy-and-composition-v0.1.md):
   #282 finished bounded terminology and adopted Samuel Mermaid v0.2,
   while public schema renaming and a common generator **did not ship**.
4. [Workflow catalog](../workflow-catalog-v0.1.md): the original 22-path
   count belongs to its historical pinned October source; the reviewed
   2026-11-05 base contains 33 workflow YAML files.
5. [Canonical architecture](../architecture.md): an *adopted at-revision*
   guide, not independent verification against the new entire main.
6. [MOOSE A/B experiment](../experiments/moose-refactor-blind-versus-codeqa-20261023.md):
   the experimental baseline was historical. As of re-check, **both**
   experimental branch refs **still exist** at their recorded commits
   and current MOOSE main is
   `a281bd07d1b61b488e22668fb8a6825417711841`.
   Earlier review text suggesting those branches were deleted was wrong
   and has been explicitly corrected.
7. [Naming v0.5 proposal](../naming-official-adoption-v05-proposal.md):
   its original pending status is historical; the independently approved
   [limited lexical policy](../naming-official-policy-v05.md) is distinct
   from #144, which closed *not planned* for broader expansion.
8. [Archived Samuel preflight](../samuel/220-controller-preflight.md):
   already carries an explicit archival/no-current-write-authority warning;
   no content change is required or authorized to inflate its scope.

## Gate and residual risks

**Allowed next action:** review the bounded documentation information
architecture and, after the current exact-head checks pass, consider its
phase-1 merge. The migration inventory still classifies **84 existing
documents as potential relocation candidates**, not already approved moves.

**Before the first physical relocation:** rerun this test on the proposed
old-to-new map; inspect direct filesystem usages outside Markdown,
cross-repository pinned references and historical deep-link anchors.
GitHub does **not** automatically redirect old Markdown URL fragments.
External backlinks, GitHub rendering and semantic validity of every
historical statement remain **not independently evaluated**; only local
references and the recorded scoped status corrections were checked.
A zero-broken-local-links result is **not** a universal documentation
truth/availability certification.
