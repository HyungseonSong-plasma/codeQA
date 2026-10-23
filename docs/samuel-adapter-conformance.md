# Pinned Samuel Python Adapter conformance (#24)

**Status:** pinned-source golden ground truth for the *existing* bounded Python
AST → CCG v0.1 adapter, not a Python semantic-completeness claim.

## Exact provenance

Source repository: `HyungseonSong-plasma/chatgpt-operation`  
Immutable source revision: `9b335e3fbb9c5e8e323e382daeec56fa25336822`

Three actual source files are copied **byte-for-byte** into
`fixtures/samuel/controller/*.py.txt` and recorded in
`fixtures/samuel/provenance.json` with their authoritative Git blob SHA-1s:

| Source | Verified Git blob |
| --- | --- |
| `src/chatgpt_operation/controller/bootstrap.py` | `0814ea249349ebcfc51e444aa5ac1dc6cf9fc9dc` |
| `src/chatgpt_operation/controller/action_lifecycle.py` | `87cc730155b52051f13ecfaa69ff717486485785` |
| `src/chatgpt_operation/controller/runtime.py` | `eadf451f09a6618525c0c481870b183c47d5602b` |

The `.py.txt` extension intentionally prevents the fixture from silently
becoming an analyzed codeQA module or a discovered Python unit test. The
conformance suite passes the text to `adapt_python_sources()` directly; it
does **not** import, execute, install or run the Samuel controller. The
dedicated CI job checks the fixture content against an additional checkout of
exact central commit using `cmp`, independently of the checked Git blob hash.

## Checked ground truth

The checked `provenance.json` identifies real classes/functions and their
exact 1-based source line positions: `BootstrapWork`, `select_controller_work`,
`ActionLifecycle`, `DispatchIntent`, `ControllerTrigger`,
`ControllerCycle`, `SamuelController`, and more. The tests verify node
kind/location and resolved `defines` witnesses.

`runtime.py` imports `ActionLifecycle`/`DispatchIntent` from
`.action_lifecycle` and `BootstrapWork`/`select_controller_work` from
`.bootstrap`. Import edges must remain `unresolved` with exactly the
source-grounded dotted target hint and original line. Even though these files
are present together, the CCG v0.1 adapter does not assert runtime import
identity or dispatch. The separate cross-module declaration-candidate view
does not silently modify this CCG claim.

## Adversarial and coverage controls

Tests include exact git-blob identity, three-file parse coverage, input-order
determinism, source location accuracy, alias and relative/star import syntax,
async definitions, decorator expression non-traversal, dynamic calls, syntax
failure, unsupported extension, missing coverage and unsafe paths.

**Supported/unsupported interface:** `docs/contracts/language-adapter-0.1.md`,
`profiles/python-adapter-capabilities-v0.1.json`,
`docs/python-adapter.md`. The caller supplies exact source bytes, repository
snapshot identity and selection. The adapter does not accept built-in
include/exclude globs, selectable feature-version settings, or arbitrary
runtime call-resolution configurations.

## Acceptance evidence

PR CI checks:
- `layout` runs the full tests including pinned golden/negative conformance.
- `self-audit` independently checks existing Python QA behavior.
- `samuel-source-conformance` checks an external exact-SHA Samuel checkout
  byte-for-byte and runs the fixture tests, without importing target modules.
- `external-audit` runs the already-pinned `moose-test-repo` cross-repo
  baseline and ensures unchanged CCG/Mechanical meaning.

A successful job is **adapter conformance evidence**, not proof of full
Python semantics, Samuel runtime correctness, or universal P1–P8 quality.
The frozen CCG v0.1 graph schema is unchanged.
