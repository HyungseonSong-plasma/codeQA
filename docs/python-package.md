# codeQA Python distribution preview (0.2.0a1)

This **preview artifact** ships a Python library, not a public release and not
a production SDK/DB/ABI compatibility certification. The codeQA repository
layout remains frozen; all distribution products are CI artifacts or local
untracked `dist/` outputs, not new committed repository-root entries.

## What gets built

The [Python Package Build and Isolated Smoke workflow](../.github/workflows/python-package.yml)
produces these artifacts from the **exact CI commit**:

- `codeqa-0.2.0a1-py3-none-any.whl`
- `codeqa-0.2.0a1.tar.gz`
- `codeqa-resource-bundle-0.2.0a1.zip`
- `SHA256SUMS` for the three files

The wheel/sdist contain `src/codeqa/` Python modules and package metadata.
The resource ZIP is **separate** and contains the original
`pyproject.toml` resource registry, only registered `profiles/` and
`contracts/`, and a deterministic `RESOURCE_MANIFEST.json` with the exact
source commit and SHA-256 values. `ResourceRegistry` still requires an
**explicit** resource root supplied by the caller; no implicit path fallback or
silent copy of repo configs is introduced.

The workflow checks both Python 3.12 and 3.13. For each, it creates isolated
virtual environments outside the repository, installs wheel and sdist
independently, checks `pip check`, imports the installed distribution with
`python -I`, checks the metadata version, verifies every bundled resource
hash, loads registered CCG/Mechanical resources from the temporary extracted
ZIP and performs one real `analyze_python` smoke test. SHA256SUMS and build
artifacts are uploaded to the run's **Artifacts** panel (30-day retention).

A separate job installs *exactly* Pydantic 2.13.5 and SQLAlchemy 2.0.50,
executes `test_dto_orm_runtime_v02.py` and fails on any skipped test.
That verifies the controlled synthetic fixture only, **not** public serializer
API or production database/migration compatibility (#92).

## Local build (no automatic publication)

```bash
python -m pip install build wheel twine
python -m build --wheel --sdist .
python -m twine check dist/*.whl dist/*.tar.gz
python .github/scripts/build_resource_bundle.py \
  --root . \
  --source-revision "$(git rev-parse HEAD)" \
  --output dist/codeqa-resource-bundle-0.2.0a1.zip
```

To install the Python library:

```bash
python -m pip install dist/codeqa-0.2.0a1-py3-none-any.whl
```

For APIs requiring `ResourceRegistry`, extract the matching ZIP into a
separate directory and pass its path explicitly:

```python
from pathlib import Path
from codeqa.infrastructure.resources import ResourceRegistry
from codeqa.pipeline.python import analyze_python

resources = ResourceRegistry(Path("/path/to/extracted/codeqa-resources"))
report = analyze_python(
    {"sample.py": "def hello():\n    return 1\n"},
    snapshot_id="my-immutable-snapshot",
    ccg_schema=resources.load_json("ccg_schema"),
    mechanical_profile=resources.load_json("mechanical_profile"),
)
print(report.summary_document())
```

Verify the download hashes before use. The resource bundle is matched to a
specific commit; mixing it with different policy or interpreter versions
is **not** verified compatibility. Draft v0.2 Naming language/SDK profiles
that are not registered in `pyproject.toml` remain repo-owned experiments
and are not silently bundled.

## Release boundary

No PyPI upload, GitHub Release publishing, automatic tag, signing claim,
platform-specific binary, MOOSE SDK bundle or source migration is part of this
work. A public distribution requires an explicit release/publishing decision,
license/metadata review and separate compatibility review.

## Installed consumer failure modes (#125)

The wheel and sdist smoke now use the shared, opt-in
`codeqa.infrastructure.resource_bundle.unpack_verified_resource_bundle`
validator. It verifies the exact version/source SHA, bundled registry against
`pyproject.toml`, every registered resource path and SHA-256, duplicate/unsafe
ZIP names, archive/destination symlinks and bounded extraction sizes **before writing files**.
No checkout-local resource fallback is added. A separate isolated-wheel CI
step corrupts the actual produced resource ZIP (wrong version/source, content
tamper, missing and extra resources) and also checks that an unknown
resource profile ID fails after unpacking the real verified bundle. All six
negative cases must fail closed. Standalone unit tests exercise additional malformed inputs.

Consumers must pin and verify the bundle against their selected package
release/commit; neither this validator nor the SHA256SUMS artifact independently
establishes an external SDK, production DB or deployed source compatibility.
Human newcomer onboarding success remains `NOT_EVALUATED`.
