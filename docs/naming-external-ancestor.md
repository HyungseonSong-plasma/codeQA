# Pinned external Python ancestor declarations — #63

**Opt-in, source-only** companion to the existing v0.1 Naming Report.
A match between a derived method spelling and an *exactly pinned declaration*
can justify protecting that spelling, but it **cannot prove** Python's actual
MRO, runtime override binding, callback invocation, method signature or
behavior. External SDK source is always caller-provided. No network/imports.

Use the registered `python_pinned_ancestor_profile` and
`pinned_ancestor_report_schema` resources and:

~~~python
parsed = parse_python_snapshot(selected_source)
naming = extract_python_naming(parsed, selected_source, snapshot_id="git:owner/repo@...")
evidence = extract_python_pinned_ancestor_evidence(
    parsed, selected_source, provider_sources,
    snapshot_id=naming.snapshot_id, profile=profile,
)
report = evaluate_pinned_ancestor_names(naming, evidence, profile)
~~~

A profile pins each provider class's fully qualified import name, exact UTF-8
source path/digest, and immutable upstream revision or SDK identity.
The adapter traverses only direct top-level single-base inheritance with
unambiguous import bindings and a closed ancestor class declaration.
Unresolved metaclasses, decorators, multiple inheritance, imported name
rebindings, dynamic base factories, inherited stub members and source
hash drift never produce a false positive override match.

Each evidence witness carries the method name/owner/line/column, exact
external class identity, pinned source digest, and the ancestor's direct
declaration line if present. `PINNED_MEMBER_DECLARED` maps to
`EXEMPT_BY_PINNED_DECLARATION` **in this companion only**, not a verified
runtime override. `PINNED_MEMBER_NOT_DECLARED` maps to `NOT_EVALUATED`:
the upstream stub may be incomplete, and this is not automatic proof that
`@override` fails. The baseline Naming v0.1 report retains its existing
`EXTERNAL_BASE_UNRESOLVED` evidence; do not silently upgrade its verdict.
The evaluator independently rejects source/profile drift, duplicate methods,
unexpected declarations and invalid location witnesses.

The synthetic `fixtures/naming-external/vendor_sdk.py.txt` source is
pinned by SHA-256, **not** a statement that a real vendor runtime was
installed or checked. Conformance tests cover qualified and renamed
imports, missing members, ambiguity, stale pins, artificial line forgery,
multiple inheritance and changed provider class bases.

This is one narrowly scoped Phase 2 capability; #64 directional DTO mapping,
#65 glossary and actual compiler/type-checker-verified inheritance remain
separate. The existing CCG/QA Result/Delta contracts are untouched.
