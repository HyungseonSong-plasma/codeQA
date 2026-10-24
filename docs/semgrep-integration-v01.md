# Semgrep external evidence adapter v0.1 — pinned JSON scan pilot (#100)

**Pilot version:** Semgrep CLI **1.182.1**, Python 3.12, isolated
local synthetic fixture on GitHub-hosted runner. No Semgrep dependency in
`pyproject.toml` and **no Semgrep subprocess inside `codeqa.core`**.
Optional external integration workflow `.github/workflows/semgrep-gate.yml`.

## Sources and trust boundary

`src/codeqa/adapters/semgrep_json.py` consumes native `semgrep scan --json`
results and preserves the **entire JSON bytes** via #98 raw-artifact digest.
Typed `STATIC_FINDING` records carry exact rule ID, path, line, message,
reported native severity and explicit v0.1 severity mapping:
`ERROR -> HIGH`, `WARNING -> MEDIUM`, `INFO -> INFO`. This mapping is a
**policy-defined ordering**, not a CVSS risk calculation.

The adapter does **not** run Semgrep, discover repository paths, fetch rules,
attest a production target, or execute arbitrary analyzed source. The caller
supplies already-selected exact path-to-SHA-256 mapping, pinned Semgrep
identity, configuration/ruleset and invocation digests, native JSON bytes,
a supported result-classifier and trusted execution receipt. Only a
version-pinned CLI orchestration can set `local_ruleset_verified=True`.
JSON alone cannot establish that an expected rule was enabled or that
Semgrep's reported `paths.scanned` is independently true.

## Supported mode

Controlled `semgrep scan --json --config=<local-file>` **without**
`--error`, metrics/version checks disabled, no Git ignore, explicit target
paths and no rule-ID rewriting. v0.1 considers `exit_code=0` to be
potentially complete **only** if the native result is structurally valid,
`errors=[]`, reported scan paths match the independently attested expected
source paths and a fixed local ruleset has been attested. This is
tool/version/mode-specific, not a generic `exit_code == 0` rule.

Different exit codes, missing/empty/truncated JSON, native errors,
unknown native severities, unknown rules or unsupported scanned-path metadata
produce `INDETERMINATE` or a hard adapter error. If adapter parsing fails,
the #99 Gate must receive **no admitted run**, returning `UNKNOWN/BLOCK`.
Already observed findings remain attached to a partial native report where
structurally valid, but do not authorize a complete/clean verdict.

A tool-specific `--error` mode may use nonzero exit for findings; **not
supported** by this pinned v0.1 mode. It must get a separate exit classifier,
not be silently reinterpreted as a successful scan.

## Exact CI proof

`.github/scripts/semgrep_gate_smoke.py`:

1. Installs/locates precisely Semgrep 1.182.1 and hashes its CLI entrypoint.
2. Creates a temporary fixture and an explicit local YAML rule `security.eval`
   against Python `eval(...)` without network rule downloads or secrets.
3. Runs a real clean scan, checks JSON `paths.scanned`, exact source digest,
   execution, rule/CLI/config fingerprints, registers typed evidence and
   evaluates #99 Gate → PASS / ALLOW.
4. Changes the isolated fixture to include `eval('1')`, repeats the real
   process; Semgrep must report the rule and the Gate → FAIL / BLOCK.
5. Re-evaluates with native artifact missing; Gate → UNKNOWN / BLOCK.
6. Runs negative fixtures from `tests/test_semgrep_adapter_v01.py`: crash,
   nonzero exit in unsupported mode, parse error, unknown source, rule-set
   mismatch, stale hashes, skipped path and multiple findings.

No machine secret is passed to the process by the smoke harness; it runs on
a dedicated, disposable GitHub-hosted Actions runner. **This is CI execution
isolation, not a general-purpose hostile code sandbox.** Do not use this
driver to scan untrusted repositories outside an appropriately secured runner.

The wheel/sdist remain independent of Semgrep. No production code is modified.

## SARIF and advanced scan scope

Semgrep can export SARIF; v0.1 ingests the native **JSON** format as the
complete typed source for tested scan coverage. A SARIF artifact can be
retained as an additional raw artifact in the orchestrator, but SARIF alone
does not independently attest complete selected-file/rule execution.
An independently versioned SARIF parser or verified dual-format parity test
is needed before claiming that arbitrary Semgrep SARIF is sufficient for
a complete Gate PASS.

**Important:** Semgrep JSON's source locations can reference the existing CCG
source selection, but they are **source anchors**, not evidence of verified
Python runtime calls. No new CCG edge is inferred.

## Separation from other issues

- #98: generic typed Envelope and independent admission;
- #99: strict scoped Gate and human authorization boundary;
- #92/#93: independent SDK/Compiler external contract verification;
- #101: persistent cache freshness and safe invalidation;
- #102: actual formal proof-to-implementation binding.

Semgrep integration does **not** imply complete security coverage, no
vulnerabilities, semantic program equivalence or verified architecture quality.
