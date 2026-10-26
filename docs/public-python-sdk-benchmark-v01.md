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
