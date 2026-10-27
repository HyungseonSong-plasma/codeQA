# Architecture QA B1 — pinned source inventory v0.1

**Status:** opt-in experimental source evidence. **Owner:** codeqa.evaluation.architecture.
**Implementation:** src/codeqa/evaluation/architecture/inventory.py.
**Contract:** contracts/qa/architecture-inventory-v0.1.schema.json.
**Tracker:** Issue #167, parent #166, design gate #165.

## Contract and authority

The pure function analyze_architecture_inventory(snapshot_sha, tracked_paths,
sources, role_policy, ...) receives a 40-character immutable Git commit SHA,
the complete caller-attested tracked-file set, source bytes/text keyed by path,
and the existing declared semantic-directory-role policy. It does not fetch
GitHub, read local files, run parsers or use any architecture questions as input.
Callers must verify the exact Git SHA and complete tracked enumeration before
using the result as real repository evidence.

The output is deterministic for the same input set, regardless of mapping or
path order. It contains a nested-directory tree, observed Python package init
markers, source SHA256 witnesses, file and language counts, role-policy-derived
ownership labels, optional filename hints, package metadata paths, a versioned
schema and an inventory fingerprint. The policy is hashed separately.

## Coverage and evidence limits

Every tracked path contributes to the denominator. A missing source byte is
MISSING. Explicit EXCLUDED and READ_FAILED paths, Git symlinks and generated
files are counted independently. The caller must identify symlinks from Git
mode 120000 and omit their bytes; no target is followed. An empty package
means a tracked init marker with no other tracked Python module, not a proof
that an empty directory exists in Git. Unsupported language source is retained
as an observed file with parser_status NOT_EVALUATED.

Ownership classes are POLICY_DECLARED (the file lies in a declared role
directory), NAME_HINT (one optional regex matches), AMBIGUOUS (multiple hint
matches) and UNCLASSIFIED. These are policy/path observations or proxy
inferences, not semantic responsibility or cohesion certifications. The
inventory never emits questions, architectural recommendations, a general
PASS verdict or a proposed source move. It does not know external callers,
runtime imports, dynamically loaded plugins or package distribution parity.

B2 will consume the tree and independently verified dependency edges; B3
will derive opportunities only from measured signals, not from preselected
Naming/Adapter questions. A later B8 orchestration step must read a real
pinned source snapshot, verify coverage and publish exact-head artifacts.
This B1 module does not claim those later capabilities are implemented.

## Validation

Tests exercise arbitrary renamed packages, stable ordering, real codeQA HEAD
tracked-file inventory, role evidence, missing/excluded/failed/generated files,
symlinks, empty Python packages, deceptive filename hints, unsafe paths,
invalid policies and JSON schema conformance. The actual-codeQA test uses
GitReader and the checkout's exact HEAD, without claiming the checkout's
untracked or ignored files are part of the tracked source denominator.

## Design dependency

PR #175 is a draft pending explicit acceptance of its proposed
codeqa.evaluation.architecture ownership and the evidence-first architecture
contract. The B1 implementation may be reviewed in parallel, but must not
be merged or represented as final B1 acceptance until #165 is approved.
