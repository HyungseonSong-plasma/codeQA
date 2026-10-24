# #92 — Real pinned Python SDK contract conformance, controlled phase 1

**Status:** Added actual external Pyright + Pydantic + SQLAlchemy CI.
**Scope:** deliberately *controlled SDK fixtures*, not production API/schema
compatibility or database migration approval.

## Controller preflight outcome and execution route

Samuel Controller in `HyungseonSong-plasma/chatgpt-operation` has typed
Issue ActionPlans, GitHub-native executor and read-only/limited repository
mutation workflows. However, its checked-in
`automation/samuel/repository-mutation-policy.json` explicitly selects
`HyungseonSong-plasma/chatgpt-operation` as the writable repository,
restricts path/branch mutations, and does not independently establish a
cross-repository codeQA mutation authorization. In addition, issue planning
can legitimately emit **no executable action plan** for an analyzed issue.

**Decision:** do not dispatch unsafe cross-repository mutations or reinterpret
the policy as authorization. Use the previously CI-proven GitHub Connector path
for codeQA branch/PR/CI operations. This records a preflight blocker of
Controller *cross-repository autonomous execution*, not of #92 source
implementation, and is not a claim that Samuel was run for codeQA.

## Exact SDK and tool versions used

- Pyright **1.1.414**, real npm CLI, with strict
  `reportIncompatibleMethodOverride=error` and active Python 3.12 environment.
- Pydantic **2.13.5** and SQLAlchemy **2.0.50**, installed and run.
- Each CI receipt records source hash, tool package/binary SHA-256,
  installed distribution metadata SHA-256, exact test outputs and rule
  coverage. The root npm Pyright package is version-pinned and hash-observed
  after installation; **transitive registry dependency hashes are not
  independently allowlisted**, so this is execution provenance rather than
  full supply-chain certification.
- The workflow fails if optional SDK tests are skipped or any selected tool
  failed. A nonzero Pyright exit with expected type diagnostics is a
  **completed analysis with findings**, not a crash.

## Positive/negative evidence and gates

`fixtures/python-sdk/valid_contract.py` exercises actual Pydantic
`BaseModel.model_validate`, `model_dump`, and a typed serializer Protocol.
It must pass Pyright.

`fixtures/python-sdk/invalid_override.py` deliberately uses an incompatible
`BaseModel.model_dump` override and an incompatible Protocol implementation;
Pyright must emit `reportIncompatibleMethodOverride` and exit with findings.
Output is parsed from the **actual JSON report**, and exact checked-rule
diagnostics are ingested into #98's typed external evidence record.
The #99 `TYPE_NO_ERRORS` policy must **PASS/ALLOW** for the valid fixture
and **FAIL/BLOCK** for the invalid fixture. No finding-free result may
pass after a crashed scan, missing source or non-attested analyzer.

In separate trusted runtime tests, Pydantic's
`AliasChoices`, `validation_alias`, `serialization_alias`,
`computed_field`, `model_dump(by_alias=True/False)` and alias
collisions are verified using a reviewed sample contract. SQLAlchemy's
ORM attribute, `Column.key`, database `Column.name`, SQLite
reflection and `before_insert` callback dispatch are exercised. An
isolated in-memory SQLite database is used; **no external DB migration** is
authorized.

## Remaining #92 acceptance

This phase cannot establish:
- Actual third-party application SDK/stub compatibility beyond the selected
  pinned libraries and tested methods.
- Full overload/mixin/metaclass/re-export/aliased-decorator coverage and
  callback semantics for an external consumer API.
- Contract accuracy for a real identified production DTO consumer or
  externally approved migration/revision window.
- Real database migration compatibility against historical and live schemas,
  with reviewed data backfills, reflection/dialect variation, inheritance and
  computed-column migration semantics.

These stay **NOT_EVALUATED** until independently pinned real consumer
contracts and migration histories are supplied and tested. Do not close #92
solely because controlled fixtures and CI pass. No v0.1 public CCG,
Naming, Mechanical or QA contract is rewritten.

**CI:** `.github/workflows/pinned-python-sdk.yml`; entrypoint
`.github/scripts/pinned_python_sdk_conformance.py`. Evidence is uploaded as
a bounded artifact with native JSON diagnostics and structured result receipt.
