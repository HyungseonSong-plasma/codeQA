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
