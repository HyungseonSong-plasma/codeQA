# MOOSE codeQA-assisted vs. blinded refactoring — controlled single-file pilot

**Date:** 2026-10-23. **Status:** two experimental branches exist; **neither
merged to moose-test-repo main**. The target is the CI guard
`ci/guards/physics_dependency_guard.py`, not a plasma solver kernel.

## Pre-registered comparison and sequencing

1. `moose-test-repo@69be07aab3e5815a1670f7308deb6caf6b49bc79` was
   read manually. Both branches were created directly from this **same SHA**.
2. **Blind** `experiment/refactor-blind-20261023` was manually refactored
   and committed as `44bed71f3bb898c099650afa011e8485fa59cb18`
   **before any codeQA run**. Change: introduce `absolute_imports` to
   consolidate duplicate AST absolute-import extraction.
3. Only after freezing Blind was codeQA run on baseline + Blind, with
   [the initial evidence run](https://github.com/HyungseonSong-plasma/codeQA/actions/runs/39952274165).
4. **Guided** `experiment/refactor-codeqa-20261023` was independently
   changed from the same baseline (not based on Blind) and committed as
   `4f4f4bc935615811ebbb6f9dc37faadc04ca6e79`.
   In response to codeQA's measured 27-line `find_cycle` function,
   the nested DFS was extracted into a top-level helper. That 27-line
   function was an observed span, **not a Mechanical threshold violation**.
5. All three frozen commits were rerun using the *same* codeQA source
   revision `ff95b021cafb535bbb1b01b4cca2f677af6c9a7c`, the same
   versioned profiles and identical selected Python guard paths. See
   [the three-arm run and differential controls](https://github.com/HyungseonSong-plasma/codeQA/actions/runs/39952912693)
   and the [machine-readable observed measurements](../../.github/experiments/moose-refactor-20261023/metrics.json).

**No code was dynamically imported or executed for the initial Blind design**.
After both designs were frozen, static codeQA analysis and the actual dependency
Guard were run. The workflow never compiles/runs the MOOSE physics solver.

## Source-backed observations

| Quantity (14 selected guard files unless stated) | Base | Blind | Guided |
| --- | ---: | ---: | ---: |
| Guard self-check `--check all` | PASS | PASS | PASS |
| Successful Python parse coverage in this **selected subset** | complete | complete | complete |
| Mechanical P1/P3 review observations | 36 | 36 | 36 |
| `find_cycle` declared source span | 27 lines | 27 lines | **10 lines** |
| `imported_modules` declared source span | 9 lines | **6 lines** | 9 lines |
| `repository_ci_references` source span | 19 lines | **17 lines** | 19 lines |
| Functions/methods observed in changed guard file | 9 | 10 | 9 |
| Changed guard lines from same baseline | — | +16/−10 | +27/−19 |
| Changed guard net lines | — | +6 | +8 |
| Observed duplicate token fraction of eligible blocks | 0.5731% | 0.5758% | 0.5702% |
| Unresolved static imports (outside selected source subset) | 71 | 71 | 71 |

The duplicate-fraction denominator is **eligible selected token blocks**,
not the same constant population between experiments. These tiny numerical
differences **must not** be interpreted as demonstrated improvement.

CodeQA's bounded P6 complexity probe reported **NOT_EVALUATED** for every
function in the changed guard: the existing analyzer excludes functions
with signature/annotation expressions. A zero *review count* here is **not**
zero complexity. The source-only Dependency metrics preserve the 71
out-of-snapshot imports rather than claiming resolved runtime coupling.

## Comparability and behavior evidence

The versioned QA Delta v0.2 returned **NOT_COMPARABLE** for
Base↔Blind, Base↔Guided and Blind↔Guided (details in the JSON):
changed function counts/denominators, unsupported/limited complexity and
static dependency coverage. This is the **correct fail-closed outcome** for
the current strict contract, not a numerical quality tie.

All three actual `physics_dependency_guard.py --check all` runs yielded
`ARCHITECTURE_DEPENDENCY_ALL_PASS`. Additional differential controls
compared exact base/Blind/Guided output for **7 synthetic cycle graphs,
81 policy direction pairs**, absolute import AST fixtures, repository CI
reference scanning, and the current complete guard audit. These controls
support bounded behavior preservation but do not establish full semantic
equivalence or scientific simulation correctness.

## Interpretation / future experiment design

- Blind primarily removed duplicate AST extraction and reduced call sites in
  `imported_modules` and `repository_ci_references`.
- Guided primarily separated the measured longest `find_cycle` wrapper
  from its DFS implementation; the extracted helper is itself 23 lines.
  Reducing one function's span does not remove those statements or
  necessarily improve maintenance outcomes.
- **Neither is proven globally superior.** No codeQA Mechanical finding
  disappeared, measured complexity remains unavailable, and QA Delta
  refuses incompatible total-population comparisons.
- A more discriminating second experiment should lock the same input scope,
  pre-register a **review-triggering** codeQA finding before the Guided
  change, specify a comparable decision unit (e.g. a stable function
  identity + source-grounded rule) and record independent behavior tests.
  Do not optimize for lowering a metric by shuffling code into helpers.
- Revisit P6's false-unavailable score for functions with annotations and
  consider a separately versioned, **subpopulation-aware** delta for
  structural refactors. Those are *future* evaluator design tasks, not
  retrospective changes to this frozen evidence.

**Repository main remains at
`69be07aab3e5815a1670f7308deb6caf6b49bc79`.**
