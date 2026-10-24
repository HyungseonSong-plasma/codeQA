# Pinned real Dafny 4.11.0 verification and generated Python receipt (#102)

**Status:** executed real external verifier/codegen **synthetic fixture** milestone.
**Not:** formal verification of a production Python/C++ implementation or a
general formal verification PASS gate.

## Exactly pinned tool and source

- Official Dafny release: `v4.11.0`, Linux x64 Ubuntu 22.04 asset
  `dafny-4.11.0-x64-ubuntu-22.04.zip`.
- Release ZIP SHA-256:
  `a46a9ff7cdd720f7955854c78e95df13f4cfe6b80691b05f8654fe19e8267179`
  from the GitHub release metadata, independently enforced with
  `sha256sum --check` and Python before running anything.
- Source file: `fixtures/formal/payment_add_one.dfy`; expected SHA-256
  `8f2558fab98a418ce9c07d8fc09befabd72e6dbe1bff32c5164eb7ac2dcd98ee`.
  The manifest `fixtures/formal/pinned-dafny-v0.1.json` is a reviewed,
  deterministic **fixture selection**, not proof of product requirements.
- Build command `dafny build --target:py payment_add_one.dfy`, verify command
  `dafny verify payment_add_one.dfy`; runner is Ubuntu 22.04, .NET 8 and
  Python 3.12.

The workflow `.github/workflows/pinned-dafny-formal.yml` installs the exact
pinned release and calls
`.github/scripts/dafny_formal_conformance.py`.
It runs the **actual external solver** and requires an explicit
`N verified, 0 errors` verifier summary with `N >= 1`.
A mutation `y := x + 2` under the *unchanged* `ensures y == x + 1`
condition MUST produce a failed verification.

## Generated implementation identity, not semantic proof

Dafny emits the Python package under `payment_add_one-py/`, including
`module_.py`, `__main__.py` and the `_dafny` runtime. The harness:

1. Locates the actual generated `__main__.py` and executes it with Python.
   The bounded expected program output is exactly `42`.
2. Builds a deterministic, path-sensitive sorted SHA-256 manifest for **every
   generated `.py` source**, not just the entry point.
3. Copies the complete generated source tree to a temporary deployment
   *fixture* and requires exact equality of the two manifests.
4. Validates the typed `FormalBinding` against exact source, generated
   and deployed bytes, toolchain ID/digest, build configuration and trusted
   caller expectations.
5. Mutates the deployment after a successful Dafny proof, then confirms
   `BINDING_BROKEN`; separately mutates the specification and confirms
   its old proof receipt cannot be treated as current.

Identity of source trees does **not** attest the correctness of Dafny's
compiler translation, a real deployment binary, libraries, or runtime
assumptions. It also cannot bind unrelated hand-written C++/Python to the
verified Dafny program. The generated Python subprocess is safe only because
the exact test source and Dafny release are pinned and the CI environment is
isolated; do not generalize this to arbitrary untrusted source execution.

## Integration with #98 and #99

The real verifier's stdout is the raw evidence artifact. Typed
`FORMAL_PROOF_RESULT` with pinned producer, rule identity, source SHA and
original stdout is admitted by #98 for **the selected Dafny source** only.

The #99 policy `FORMAL_IMPLEMENTATION_VERIFIED` is evaluated with this run
and is deliberately required to result in `UNKNOWN / BLOCK`. A source-level
proof + generated-byte identity is not promoted to a blanket production code
certification. This is a **negative/limited-scope E2E Gate conformance**;
the remaining positive production binding and domain-policy acceptance are
tracked in #102.

The CI job uploads `formal-evidence.json`, verification logs, negative
verification log, codegen log and the generated Python fixture tree as a
short-lived artifact. The receipt includes its assumptions and limitations.
The GitHub runner and its environmental metadata are **not independently
cryptographically signed** by this module.

## Follow-up for full #102 acceptance

Formal production Gate promotion requires a separately reviewed v0.2
contract binding precise verified properties, trusted axioms, compiler/runtime
and code-generation assumptions, code and deployment identity, exact user
requirement coverage, plus independent positive and negative end-to-end
acceptance. Until then `UNKNOWN/BLOCK` is the only safe v0.1 formal
implementation outcome. The current release is **not** a verified production
payment system.
