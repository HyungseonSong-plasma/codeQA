# #92 — Independently pinned real Python SDK benchmark (source phase)

**Named SDK:** Stripe Python SDK **16.0.0**, upstream
`stripe/stripe-python` at immutable commit
`89e8528a61d838600097ffe5c9615c9b7d35778a`, tree
`4917f33f5364e856e21dbce4eddeef5124580149` (MIT).
**Named consumer:** the same upstream repository's real
`examples/webhooks.py` Flask webhook handler.

The versioned inventory
`fixtures/python-sdk/public-python-sdk-benchmark-v0.1.json` pins **10**
exact source/consumer files by Git object SHA-1 and SHA-256: project
metadata, SDK version, `stripe/__init__.py`, `_ephemeral_key.py`,
`_util.py`, create/delete resource bases, `_webhook.py`, consumer
example and license. The source-only
`.github/scripts/public_python_sdk_benchmark.py` validates the
immutable upstream commit/tree link and all selected bytes. It inspects
real AST evidence of two `EphemeralKey.delete` overload declarations,
multiple resource inheritance, the `class_method_variant` descriptor,
the `Webhook` re-export, and the Flask consumer's
`Webhook.construct_event` call and `@app.route` registration.
Eight negative controls deliberately remove or forge selected
source/consumer evidence.

**Evidence classification:** `STATIC_DECLARATION_MATCH` for only
these selected syntax facts. A Flask callback *registration* is not
runtime dispatch proof. `Webhook` re-export within a
`TYPE_CHECKING` branch is not runtime import proof.
`class_method_variant` is a dynamic descriptor, not a verified
signature-preserving decorator for all invocation forms.
The actual SDK metaclass, independently executed Pyright override
and Protocol/overload compatibility, full SDK install/dependency
compatibility, and webhook dispatch are all **`NOT_EVALUATED`**.
The existing real Pyright 1.1.414 positive/negative tests apply only
to controlled Pydantic fixtures, not to this Stripe source.

The benchmark is read-only. It **does not execute, import, install, or
run arbitrary upstream code**, does not call Stripe APIs, requires no
credentials, and makes no production compatibility claim. The next
independent milestone is a vetted isolated environment with a pinned
Stripe distribution whose installed file hashes are independently
matched to the selected source, and a real Pyright run against an
exact-source named consumer/typed negative controls; classify all
uncovered patterns as `NOT_EVALUATED` rather than claiming PASS.
Issue #92 remains OPEN and Draft PRs require human review.

## Release-tag versus selected source commit

Independently inspected annotated upstream `v16.0.0` tag resolves to
commit `29363094b09a67f8b1b50f577b463edbbb27ec9a`, tree
`d11d37ace1173fb7dfb4d66afa29b4b9a6760f4c`. This differs from
the selected newer source commit despite both declaring version
`16.0.0`. In particular, `stripe/_util.py` has release-tag blob
`8b378c63c880eda7180a025ec8d9f745895f619f` versus selected
`e034b209fa5d6284759ab10a50ba3bbd84e200a7`, and
`stripe/_webhook.py` has release-tag blob
`9fc269e691b6566e804d19132ef79b2d270f4da8` versus selected
`a9a041454c80c5996352adb0a5a47222422187d9`.
Therefore this benchmark attests **the exact selected Git source**, not
equivalence to the published PyPI `stripe==16.0.0` wheel. A future
typechecker run against an installed wheel must independently bind its
bytes to an approved release-tag/source snapshot, or report
`UNRESOLVED` rather than transferring this source-only PASS.

## Partial real Pyright execution (separate from SDK compatibility)

The same CI invokes actual pinned **Pyright 1.1.414** on byte-identical
copies of the selected real `stripe/_ephemeral_key.py` source and
`examples/webhooks.py` consumer, with the other eight selected sources
copied alongside. The exact selected source set and all copied bytes
are checked before accepting native Pyright JSON. Tool crashes,
malformed reports, mismatched exit/error counts, foreign diagnostic
paths and incomplete source scan counts fail CI. The native report
`public-python-sdk-pyright-native.json` and digest are uploaded.

**Classification: `EXECUTED_PARTIAL_SOURCE_ONLY`.** This is deliberately
an incomplete package tree without full Stripe dependencies or Flask.
Native missing-import/type diagnostics are recorded, **not** interpreted
as actual API incompatibility. Zero diagnostics would likewise not
establish full SDK compatibility. Override/Protocol conformance,
metaclass behavior, callback dispatch, complete dependency closure and
installed wheel equivalence remain `NOT_EVALUATED`. This does not
replace the independently pinned installed SDK and real consumer
conformance still required for issue closure.


## Machine-verifiable release-tag identity boundary (2026-10-26)

The selected source snapshot has `pyproject.toml` version `16.0.0`, but **it is not the same Git tree as the annotated `v16.0.0` release**. The new `release_tag` evidence records the independently fetched annotated tag object `8f2bd3f5bf2e21553b08bb0d47f0a3984a576e47` → release commit `29363094b09a67f8b1b50f577b463edbbb27ec9a` → tree `d11d37ace1173fb7dfb4d66afa29b4b9a6760f4c`. Of the **same 10 selected files**, **8 Git blobs match** and **2 differ**: `stripe/_util.py` and `stripe/_webhook.py`. This is a real selected-source mismatch, not a Pyright or SDK compatibility verdict.

The read-only CI now independently checks the live annotated tag ref, tag object, commit/tree identity and all ten release-tag blob identities against the versioned manifest; it rejects moved tags, missing/truncated trees, forged blob identities and a false source-equivalence claim. Three pure negative controls deliberately forge release identity, expected drift and file coverage. The JSON receipt records `RELEASE_TAG_ATTESTED_SOURCE_MISMATCH`, **not** installed release wheel equivalence. No PyPI wheel was installed or authenticated for this release-tag witness; runtime/API/consumer/override compatibility remain `NOT_EVALUATED`. Existing source-only Stripe snapshot and partial Pyright checks remain separate and unchanged.

## Full pinned-repository Pyright receipt: bounded interpretation

A separate read-only stage fetches the **exact** selected Stripe Git commit into an isolated temporary checkout with Git hooks and submodule recursion disabled. It verifies the checkout commit/tree and all ten selected source bytes, then invokes real pinned Pyright **1.1.414** with strict mode and explicit `examples/webhooks.py` and `stripe/_ephemeral_key.py` include targets. The native JSON receipt is saved as `public-python-sdk-full-source-pyright.json`, with its SHA-256, tool version, total `filesAnalyzed`, diagnostic counts and rule histogram. **This is a static typechecker invocation, not execution of upstream Python code or a verified installed SDK wheel.**

The receipt status `EXECUTED_PINNED_REPOSITORY_SOURCE` means only that this exact Git checkout and typechecker invocation completed with internally consistent native JSON. Native diagnostics must refer to real in-checkout files and **valid zero-based source lines**; missing range, invalid line, foreign path, unknown severity and missing files fail closed. Pure adversarial tests run in the pinned SDK workflow before network-dependent conformance. The `filesAnalyzed` aggregate does **not** independently prove that every named include target was scanned; the explicit `analyzed_target_path_set=NOT_INDEPENDENTLY_ATTESTED` field prevents that promotion. Third-party dependency closure, installed wheel equivalence, complete overload/override/Protocol and callback semantics, and runtime compatibility remain `NOT_EVALUATED`. A nonzero error count is a **native tool finding**, not a demonstrated SDK incompatibility.

## CI GitHub REST rate-limit and credential isolation

A real [source-head pinned SDK run #40305501269](https://github.com/HyungseonSong-plasma/codeQA/actions/runs/40305501269) failed at **HTTP 403 anonymous GitHub REST API rate limit** before public FastAPI source attestation; the new five pure native-diagnostic tests had already passed. This was a network evidence acquisition failure, **not** an observed public API/SDK incompatibility or passing full conformance.

The next revision uses the Actions-provided **built-in read-only `github.token`** solely for HTTPS `api.github.com` commit/tree attestation requests; raw source downloads remain unauthenticated, and unexpected hosts, userinfo, ports and redirects are rejected before credentials can be forwarded. Git checkout and both partial/full Pyright subprocesses explicitly **strip `GITHUB_TOKEN` and `GH_TOKEN`** from their environment. No user-supplied API key, production credential, external write permission or private data is required. The new token-boundary unit tests use only a synthetic string and make no network requests. Actual source-attestation CI must be rerun at the new exact head before claiming PASS; a further 403 or unavailable upstream remains a hard failure/NOT_EVALUATED, not a silent fallback.


## Native Pyright UTF-16 diagnostic span integrity (2026-10-27)

The full pinned Stripe source scan now validates both the start and end of
every reported native Pyright range, including line/character presence,
strict non-boolean integer coordinates, UTF-16 code-unit column bounds,
in-source line coordinates, and non-reversed spans. Negative controls cover
missing endpoints, fabricated out-of-range offsets, booleans, and reversed
multi-line spans; a non-BMP character verifies UTF-16 rather than Python
code-point indexing. This guards the fidelity of **reported diagnostics**.

**This is not full analyzed-target coverage, installed-wheel source
equivalence, an independently resolved third-party dependency set,
runtime callback semantics, deployed API consumer compatibility or
production database migration verification.** All those statuses remain
\`NOT_EVALUATED\` until independently evidenced.
