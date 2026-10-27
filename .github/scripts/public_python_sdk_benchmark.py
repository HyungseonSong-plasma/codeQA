#!/usr/bin/env python3
"""#92: independent real Python SDK source witness; no upstream execution.

Static declaration matches do NOT establish Pyright override conformance or
runtime webhook/callback dispatch. Those remain explicitly NOT_EVALUATED.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import tomllib

from public_api_benchmark import fetch_pinned, git_blob, require

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "fixtures/python-sdk/public-python-sdk-benchmark-v0.1.json"


def unprivileged_analyzer_env() -> dict[str, str]:
    """Remove GitHub REST credentials from Git and third-party Pyright tools."""
    return {key: value for key, value in os.environ.items()
            if key not in {"GITHUB_TOKEN", "GH_TOKEN"}}


def attest(manifest: dict, sources: dict[str, bytes], tree: dict[str, str]) -> None:
    require(manifest["benchmark"] == "stripe/stripe-python"
            and manifest["commit"] == "89e8528a61d838600097ffe5c9615c9b7d35778a"
            and manifest["tree"] == "4917f33f5364e856e21dbce4eddeef5124580149"
            and manifest["scope"] == "PINNED_REAL_PYTHON_SDK_SOURCE_ONLY",
            "PYTHON_SDK_SELECTION_DRIFT")
    files = manifest["files"]
    require(len(files) == 10 and len({row[0] for row in files}) == 10
            and set(row[0] for row in files) == set(sources),
            "PYTHON_SDK_SOURCE_SET_DRIFT")
    for path, blob, digest in files:
        raw = sources[path]
        require(tree.get(path) == blob and git_blob(raw) == blob
                and hashlib.sha256(raw).hexdigest() == digest,
                "PYTHON_SDK_SOURCE_DIGEST_DRIFT " + path)


def inspect(manifest: dict, sources: dict[str, bytes]) -> dict:
    def parse(path: str) -> ast.Module:
        return ast.parse(sources[path].decode("utf-8"), filename=path)
    project = tomllib.loads(sources["pyproject.toml"].decode())["project"]
    require(project["name"] == "stripe"
            and project["version"] == manifest["sdk_version"] == "16.0.0"
            and sources["LICENSE"].startswith(b"The MIT License"),
            "PYTHON_SDK_PACKAGE_VERSION_OR_LICENSE_DRIFT")
    version = parse("stripe/_version.py")
    require(any(isinstance(n, ast.Assign) and any(
        isinstance(t, ast.Name) and t.id == "VERSION" for t in n.targets)
        and ast.literal_eval(n.value) == "16.0.0" for n in version.body),
        "PYTHON_SDK_RUNTIME_VERSION_DRIFT")
    ephemeral = parse("stripe/_ephemeral_key.py")
    klass = next((n for n in ephemeral.body
                  if isinstance(n, ast.ClassDef) and n.name == "EphemeralKey"), None)
    require(klass is not None, "PYTHON_SDK_RESOURCE_MISSING")
    bases = {b.value.id for b in klass.bases if isinstance(b, ast.Subscript)
             and isinstance(b.value, ast.Name)}
    require({"CreateableAPIResource", "DeletableAPIResource"}.issubset(bases),
            "PYTHON_SDK_MULTIPLE_INHERITANCE_DRIFT")
    deletes = [n for n in klass.body if isinstance(n, ast.FunctionDef)
               and n.name == "delete"]
    overloads = [n for n in deletes if any(
        isinstance(d, ast.Name) and d.id == "overload" for d in n.decorator_list)]
    aliased = [n for n in deletes if any(
        isinstance(d, ast.Call) and isinstance(d.func, ast.Name)
        and d.func.id == "class_method_variant"
        and d.args and isinstance(d.args[0], ast.Constant)
        and d.args[0].value == "_cls_delete" for d in n.decorator_list)]
    require(len(overloads) == 2 and len(aliased) == 1,
            "PYTHON_SDK_OVERLOAD_DECORATOR_DRIFT")
    util = parse("stripe/_util.py")
    descriptor = next((n for n in util.body if isinstance(n, ast.ClassDef)
                       and n.name == "class_method_variant"), None)
    require(descriptor is not None
            and {"__call__", "__get__"}.issubset({
                n.name for n in descriptor.body if isinstance(n, ast.FunctionDef)}),
            "PYTHON_SDK_ALIASED_DECORATOR_IMPLEMENTATION_MISSING")
    exports = parse("stripe/__init__.py")
    require(any(isinstance(n, ast.ImportFrom) and n.module == "stripe._webhook"
                and {"Webhook", "WebhookSignature"}.issubset(
                    {a.name for a in n.names if a.asname == a.name}) for n in ast.walk(exports)),
            "PYTHON_SDK_REEXPORT_DRIFT")
    webhook = parse("stripe/_webhook.py")
    wclass = next((n for n in webhook.body
                   if isinstance(n, ast.ClassDef) and n.name == "Webhook"), None)
    require(wclass is not None and any(
        isinstance(n, ast.FunctionDef) and n.name == "construct_event"
        for n in wclass.body), "PYTHON_SDK_WEBHOOK_METHOD_MISSING")
    consumer = parse("examples/webhooks.py")
    require(any(isinstance(n, ast.ImportFrom) and n.module == "stripe"
                and {"Webhook", "SignatureVerificationError"}.issubset(
                    {a.name for a in n.names}) for n in consumer.body),
            "PYTHON_SDK_NAMED_CONSUMER_IMPORT_DRIFT")
    calls = [n for n in ast.walk(consumer) if isinstance(n, ast.Call)]
    require(any(isinstance(n.func, ast.Attribute) and n.func.attr == "construct_event"
                and isinstance(n.func.value, ast.Name)
                and n.func.value.id == "Webhook" for n in calls),
            "PYTHON_SDK_CONSUMER_CALL_DRIFT")
    require(any(isinstance(n, ast.FunctionDef) and n.name == "webhooks"
                and any(isinstance(d, ast.Call)
                        and isinstance(d.func, ast.Attribute)
                        and d.func.attr == "route" for d in n.decorator_list)
                for n in consumer.body),
            "PYTHON_SDK_CALLBACK_REGISTRATION_DRIFT")
    return {"benchmark": manifest["benchmark"], "commit": manifest["commit"],
            "sdk_version": manifest["sdk_version"],
            "consumer": manifest["named_consumer"],
            "static_observations": {
                "overload_declarations": len(overloads),
                "aliased_decorator": "STATIC_DECLARATION_MATCH",
                "multiple_inheritance": sorted(bases),
                "reexport": "STATIC_DECLARATION_MATCH",
                "webhook_consumer": "STATIC_DECLARATION_MATCH"},
            "metaclass": "NOT_EVALUATED",
            "callback_dispatch": "NOT_EVALUATED",
            "real_pyright_override": "NOT_EVALUATED",
            "runtime_compatibility": "NOT_EVALUATED",
            "upstream_execution": "NOT_PERFORMED"}


def negative_controls(manifest: dict, sources: dict[str, bytes], tree: dict[str, str]) -> int:
    cases = []
    def mutated(path: str, before: str, after: str) -> dict[str, bytes]:
        src = sources[path].decode()
        require(before in src, "NEGATIVE_TARGET_NOT_FOUND")
        return {**sources, path: src.replace(before, after, 1).encode()}
    def reject(label: str, call) -> None:
        try:
            call()
        except (RuntimeError, SyntaxError, ValueError):
            cases.append(label)
        else:
            raise RuntimeError("SDK_NEGATIVE_ACCEPTED " + label)
    reject("source_tamper", lambda: attest(manifest, mutated(
        "stripe/_version.py", '16.0.0', '99.0.0'), tree))
    reject("missing_consumer", lambda: attest(manifest, {
        k: v for k, v in sources.items() if k != "examples/webhooks.py"}, tree))
    reject("missing_overload", lambda: inspect(manifest, mutated(
        "stripe/_ephemeral_key.py", "@overload", "# @overload")))
    reject("wrong_alias_decorator", lambda: inspect(manifest, mutated(
        "stripe/_ephemeral_key.py", '@class_method_variant("_cls_delete")',
        '@class_method_variant("_cls_other")')))
    reject("broken_reexport", lambda: inspect(manifest, mutated(
        "stripe/__init__.py", "Webhook as Webhook,", "Webhook as OtherWebhook,")))
    reject("missing_consumer_call", lambda: inspect(manifest, mutated(
        "examples/webhooks.py", "Webhook.construct_event(", "Webhook.other_event(")))
    reject("missing_callback", lambda: inspect(manifest, mutated(
        "examples/webhooks.py", '@app.route("/webhooks", methods=["POST"])',
        '# @app.route("/webhooks", methods=["POST"])')))
    reject("missing_mixin", lambda: inspect(manifest, mutated(
        "stripe/_ephemeral_key.py", 'DeletableAPIResource["EphemeralKey"],',
        'object,')))
    return len(cases)



def compare_release_selection(manifest: dict, observed_blobs: dict[str, str]) -> dict:
    """Fail closed if release-tag source is silently equated to a dev snapshot."""
    selected = {path: blob for path, blob, _ in manifest["files"]}
    release = manifest["release_tag"]
    expected = release["selected_blobs"]
    require(set(selected) == set(expected) == set(observed_blobs),
            "RELEASE_SELECTED_FILE_SET_DRIFT")
    require(all(isinstance(blob, str) and len(blob) == 40
                and all(c in "0123456789abcdef" for c in blob)
                for blob in expected.values()), "RELEASE_BLOB_IDENTITY_INVALID")
    require(all(observed_blobs[path] == expected[path] for path in selected),
            "RELEASE_SELECTED_BLOB_MISMATCH")
    drift = sorted(path for path in selected if selected[path] != observed_blobs[path])
    require(drift == release["expected_drift_paths"]
            and drift == ["stripe/_util.py", "stripe/_webhook.py"],
            "RELEASE_SOURCE_EQUIVALENCE_DRIFT")
    require(release["wheel_equivalence"] == "NOT_EVALUATED",
            "RELEASE_WHEEL_PROOF_FORGED")
    return {"status": "RELEASE_TAG_ATTESTED_SOURCE_MISMATCH",
            "tag": release["tag"], "tag_commit": release["commit"],
            "tag_tree": release["tree"], "selected_files": len(selected),
            "matching_selected_files": len(selected) - len(drift),
            "mismatched_selected_files": len(drift), "mismatched_paths": drift,
            "observed_selected_blobs": observed_blobs,
            "installed_wheel_equivalence": "NOT_EVALUATED"}


def attest_release_tag(manifest: dict) -> dict:
    """Read-only GitHub annotated tag→commit→tree attestation; no upstream code."""
    from public_api_benchmark import request_bytes
    release = manifest["release_tag"]
    repo = manifest["benchmark"]
    require(repo == "stripe/stripe-python" and release["tag"] == "v16.0.0",
            "RELEASE_SELECTION_DRIFT")
    base = "https://api.github.com/repos/" + repo + "/git/"
    ref = json.loads(request_bytes(base + "ref/tags/v16.0.0"))
    require(ref.get("ref") == "refs/tags/v16.0.0"
            and ref.get("object", {}).get("type") == "tag"
            and ref["object"].get("sha") == release["annotated_tag_object_sha"],
            "RELEASE_TAG_OBJECT_DRIFT")
    tag = json.loads(request_bytes(base + "tags/" + release["annotated_tag_object_sha"]))
    require(tag.get("sha") == release["annotated_tag_object_sha"]
            and tag.get("tag") == release["tag"]
            and tag.get("object", {}).get("type") == "commit"
            and tag["object"].get("sha") == release["commit"],
            "RELEASE_TAG_COMMIT_DRIFT")
    commit = json.loads(request_bytes(base + "commits/" + release["commit"]))
    require(commit.get("sha") == release["commit"]
            and commit.get("tree", {}).get("sha") == release["tree"],
            "RELEASE_TAG_TREE_DRIFT")
    tree = json.loads(request_bytes(base + "trees/" + release["tree"] + "?recursive=1"))
    require(tree.get("sha") == release["tree"] and tree.get("truncated") is False,
            "RELEASE_TREE_INCOMPLETE")
    entries = {row["path"]: row["sha"] for row in tree["tree"]
               if row["type"] == "blob"}
    selected = {path: entries[path] for path, _, _ in manifest["files"]
                if path in entries}
    return compare_release_selection(manifest, selected)


def release_negative_controls(manifest: dict, observed: dict[str, str]) -> int:
    from copy import deepcopy
    cases = []
    bad = deepcopy(manifest)
    bad["release_tag"]["selected_blobs"]["stripe/_util.py"] = "0" * 40
    cases.append(("forged_release_blob", bad, observed))
    bad = deepcopy(manifest)
    bad["release_tag"]["expected_drift_paths"] = []
    cases.append(("forged_source_equivalence", bad, observed))
    cases.append(("missing_release_file", manifest,
                  {k: v for k, v in observed.items() if k != "stripe/_webhook.py"}))
    for label, fixture, actual in cases:
        try:
            compare_release_selection(fixture, actual)
        except RuntimeError:
            continue
        raise RuntimeError("RELEASE_NEGATIVE_ACCEPTED " + label)
    return len(cases)

def run_partial_pyright(sources: dict[str, bytes], binary: Path, output: Path) -> dict:
    """Run actual Pyright on exact source bytes, with unresolved imports explicit."""
    require(binary.is_file(), "EXTERNAL_PYRIGHT_MISSING")
    selected = ("examples/webhooks.py", "stripe/_ephemeral_key.py")
    with tempfile.TemporaryDirectory(prefix="codeqa-real-stripe-source-") as tmp:
        project = Path(tmp)
        for path, raw in sources.items():
            target = project / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
        config = {"typeCheckingMode": "strict", "include": list(selected),
                  "extraPaths": ["."], "reportMissingImports": "error"}
        (project / "pyrightconfig.json").write_text(
            json.dumps(config, sort_keys=True), encoding="utf-8")
        completed = subprocess.run(
            [str(binary.resolve()), "--project", str(project), "--pythonpath",
             sys.executable, "--outputjson"],
            cwd=ROOT, capture_output=True, text=True, check=False, timeout=120,
            env=unprivileged_analyzer_env())
        require(completed.returncode in (0, 1), "EXTERNAL_PYRIGHT_TOOL_CRASH")
        try:
            native = json.loads(completed.stdout)
        except ValueError as exc:
            raise RuntimeError("EXTERNAL_PYRIGHT_INVALID_JSON") from exc
        require(isinstance(native, dict) and native.get("version") == "1.1.414"
                and isinstance(native.get("generalDiagnostics"), list)
                and isinstance(native.get("summary"), dict)
                and not native.get("fatalErrorOccurred")
                and not native.get("configParseErrorOccurred"),
                "EXTERNAL_PYRIGHT_INCOMPLETE")
        count = native["summary"].get("errorCount")
        analyzed = native["summary"].get("filesAnalyzed")
        require(type(count) is int and count >= 0
                and type(analyzed) is int and analyzed >= len(selected),
                "EXTERNAL_PYRIGHT_INCOMPLETE_COVERAGE")
        errors = [d for d in native["generalDiagnostics"]
                  if isinstance(d, dict) and d.get("severity") == "error"]
        require(count == len(errors)
                and (completed.returncode == 1) == bool(count),
                "EXTERNAL_PYRIGHT_INCONSISTENT_EXIT")
        for diag in native["generalDiagnostics"]:
            require(isinstance(diag, dict) and isinstance(diag.get("file"), str),
                    "EXTERNAL_PYRIGHT_MALFORMED_DIAGNOSTIC")
            path = Path(diag["file"])
            resolved = (path if path.is_absolute() else project / path).resolve()
            require(resolved.is_relative_to(project.resolve())
                    and resolved.relative_to(project.resolve()).as_posix() in sources,
                    "EXTERNAL_PYRIGHT_FOREIGN_DIAGNOSTIC")
        require(all((project / p).read_bytes() == raw for p, raw in sources.items()),
                "EXTERNAL_PYRIGHT_SOURCE_MUTATED")
        output.mkdir(parents=True, exist_ok=True)
        raw = completed.stdout.encode("utf-8")
        (output / "public-python-sdk-pyright-native.json").write_bytes(raw)
    # This partial SDK tree intentionally lacks most Stripe modules and Flask.
    # Even a zero-error scan cannot prove a complete installed SDK contract.
    print("PYRIGHT_EXTERNAL_SDK=EXECUTED_PARTIAL errors=" + str(count)
          + " filesAnalyzed=" + str(analyzed)
          + " full_dependency_closure=NOT_EVALUATED")
    return {"status": "EXECUTED_PARTIAL_SOURCE_ONLY", "version": "1.1.414",
            "selected_files": list(selected), "files_analyzed": analyzed,
            "errors": count, "exit_code": completed.returncode,
            "native_json_sha256": hashlib.sha256(raw).hexdigest(),
            "full_dependency_closure": "NOT_EVALUATED",
            "override_compatibility": "NOT_EVALUATED",
            "callback_dispatch": "NOT_EVALUATED"}



def validate_full_source_diagnostic(diagnostic: object, repo: Path) -> None:
    """Check real Pyright UTF-16 source-range locations, not scan coverage.

    A valid location is no proof of type soundness or complete target analysis.
    """
    require(isinstance(diagnostic, dict)
            and diagnostic.get("severity") in {"error", "warning", "information"}
            and isinstance(diagnostic.get("file"), str)
            and bool(diagnostic["file"]),
            "FULL_SOURCE_PYRIGHT_MALFORMED_DIAGNOSTIC")
    location = Path(diagnostic["file"])
    actual = (location if location.is_absolute() else repo / location).resolve()
    require(actual.is_relative_to(repo.resolve()) and actual.is_file(),
            "FULL_SOURCE_PYRIGHT_FOREIGN_DIAGNOSTIC")
    span = diagnostic.get("range")
    require(isinstance(span, dict)
            and isinstance(span.get("start"), dict)
            and isinstance(span.get("end"), dict),
            "FULL_SOURCE_PYRIGHT_MALFORMED_RANGE")
    start, end = span["start"], span["end"]
    for point in (start, end):
        require(type(point.get("line")) is int
                and type(point.get("character")) is int,
                "FULL_SOURCE_PYRIGHT_MALFORMED_RANGE")

    # Pyright uses zero-based UTF-16 code-unit offsets (not Python str
    # indices); only the selected, independently fetched source is read.
    try:
        lines = actual.read_text(encoding="utf-8").split("\n")
    except UnicodeError as exc:
        raise RuntimeError("FULL_SOURCE_PYRIGHT_UNREADABLE_SOURCE") from exc
    for point in (start, end):
        line, column = point["line"], point["character"]
        require(0 <= line < len(lines),
                "FULL_SOURCE_PYRIGHT_RANGE_OUTSIDE_SOURCE")
        body = lines[line].removesuffix("\r")
        utf16_columns = len(body.encode("utf-16-le")) // 2
        require(0 <= column <= utf16_columns,
                "FULL_SOURCE_PYRIGHT_RANGE_OUTSIDE_SOURCE")
    require((end["line"], end["character"])
            >= (start["line"], start["character"]),
            "FULL_SOURCE_PYRIGHT_REVERSED_RANGE")


def run_full_repository_pyright(manifest: dict, sources: dict[str, bytes],
                              binary: Path, output: Path) -> dict:
    """Git-fetch immutable public source in an isolated temp tree; never import it.

    Only Git checkout and static Pyright analysis are performed. No upstream
    install scripts, tests, imports, hooks, submodules, or API calls execute.
    """
    import os
    with tempfile.TemporaryDirectory(prefix="codeqa-stripe-pinned-git-") as tmp:
        repo = Path(tmp) / "upstream"
        repo.mkdir()
        env = {**unprivileged_analyzer_env(), "GIT_LFS_SKIP_SMUDGE": "1",
               "GIT_TERMINAL_PROMPT": "0"}
        commands = [
            ["git", "-c", "core.hooksPath=/dev/null", "init", "-q", str(repo)],
            ["git", "-C", str(repo), "-c", "core.hooksPath=/dev/null",
             "-c", "submodule.recurse=false", "fetch", "--depth=1",
             "https://github.com/stripe/stripe-python.git", manifest["commit"]],
            ["git", "-C", str(repo), "-c", "core.hooksPath=/dev/null",
             "-c", "submodule.recurse=false", "checkout", "-q", "--detach", "FETCH_HEAD"],
        ]
        for command in commands:
            done = subprocess.run(command, capture_output=True, text=True,
                                  check=False, timeout=120, env=env)
            require(done.returncode == 0,
                    "PINNED_SDK_GIT_READ_FAILED " + done.stderr[-400:])
        def rev(*args: str) -> str:
            run = subprocess.run(["git", "-C", str(repo), "rev-parse", *args],
                                 capture_output=True, text=True,
                                 check=False, timeout=20, env=env)
            require(run.returncode == 0, "PINNED_SDK_GIT_IDENTITY_ERROR")
            return run.stdout.strip()
        require(rev("HEAD") == manifest["commit"]
                and rev("HEAD^{tree}") == manifest["tree"],
                "PINNED_SDK_GIT_COMMIT_TREE_MISMATCH")
        for path, raw in sources.items():
            target = repo / path
            require(target.is_file() and target.resolve().is_relative_to(repo.resolve())
                    and target.read_bytes() == raw,
                    "PINNED_SDK_CHECKOUT_SOURCE_DRIFT " + path)
        config = {"typeCheckingMode": "strict",
                  "include": ["examples/webhooks.py", "stripe/_ephemeral_key.py"],
                  "extraPaths": ["."], "reportMissingImports": "error"}
        (repo / "pyrightconfig.json").write_text(
            json.dumps(config, sort_keys=True), encoding="utf-8")
        done = subprocess.run(
            [str(binary.resolve()), "--project", str(repo), "--pythonpath",
             sys.executable, "--outputjson"],
            cwd=ROOT, capture_output=True, text=True, check=False, timeout=180,
            env=unprivileged_analyzer_env())
        require(done.returncode in (0, 1), "FULL_SOURCE_PYRIGHT_CRASH")
        try:
            native = json.loads(done.stdout)
        except ValueError as exc:
            raise RuntimeError("FULL_SOURCE_PYRIGHT_INVALID_JSON") from exc
        require(native.get("version") == "1.1.414"
                and isinstance(native.get("summary"), dict)
                and isinstance(native.get("generalDiagnostics"), list)
                and not native.get("fatalErrorOccurred")
                and not native.get("configParseErrorOccurred"),
                "FULL_SOURCE_PYRIGHT_INCOMPLETE")
        count = native["summary"].get("errorCount")
        analyzed = native["summary"].get("filesAnalyzed")
        require(type(count) is int and type(analyzed) is int and analyzed >= 2,
                "FULL_SOURCE_PYRIGHT_MISSING_COVERAGE")
        errors = [x for x in native["generalDiagnostics"]
                  if isinstance(x, dict) and x.get("severity") == "error"]
        require(count == len(errors) and (done.returncode == 1) == bool(count),
                "FULL_SOURCE_PYRIGHT_EXIT_MISMATCH")
        for diagnostic in native["generalDiagnostics"]:
            validate_full_source_diagnostic(diagnostic, repo)
        require(all((repo / p).read_bytes() == raw for p, raw in sources.items()),
                "FULL_SOURCE_PYRIGHT_MUTATED_SELECTED_SOURCE")
        raw = done.stdout.encode()
        output.mkdir(parents=True, exist_ok=True)
        (output / "public-python-sdk-full-source-pyright.json").write_bytes(raw)
    rule_counts = {}
    for diagnostic in errors:
        rule = diagnostic.get("rule") or "UNCLASSIFIED"
        rule_counts[rule] = rule_counts.get(rule, 0) + 1
    print("PYRIGHT_STRIPE_FULL_SOURCE=EXECUTED errors=" + str(count)
          + " filesAnalyzed=" + str(analyzed)
          + " rules=" + json.dumps(rule_counts, sort_keys=True)
          + " dependency_closure=NOT_EVALUATED runtime=NOT_EXECUTED")
    return {"status": "EXECUTED_PINNED_REPOSITORY_SOURCE",
            "diagnostic_rule_counts": rule_counts,
            "version": "1.1.414", "commit": manifest["commit"],
            "tree": manifest["tree"], "files_analyzed": analyzed,
            "errors": count, "exit_code": done.returncode,
            "native_json_sha256": hashlib.sha256(raw).hexdigest(),
            "analyzed_target_path_set": "NOT_INDEPENDENTLY_ATTESTED",
            "third_party_dependency_closure": "NOT_EVALUATED",
            "installed_wheel_identity": "NOT_EVALUATED",
            "override_compatibility": "NOT_EVALUATED",
            "runtime_callback_dispatch": "NOT_EVALUATED"}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--pyright", type=Path, required=True)
    args = p.parse_args()
    manifest = json.loads(MANIFEST.read_bytes())
    sources, tree = fetch_pinned(manifest)
    attest(manifest, sources, tree)
    result = inspect(manifest, sources)
    result["negative_controls"] = negative_controls(manifest, sources, tree)
    result["release_tag"] = attest_release_tag(manifest)
    result["release_negative_controls"] = release_negative_controls(
        manifest, result["release_tag"]["observed_selected_blobs"])
    result["partial_typechecker"] = run_partial_pyright(sources, args.pyright, args.output)
    result["full_source_typechecker"] = run_full_repository_pyright(
        manifest, sources, args.pyright, args.output)
    result["manifest_sha256"] = hashlib.sha256(MANIFEST.read_bytes()).hexdigest()
    result["source_files"] = [{"path": p, "git_blob": b, "sha256": h}
                              for p, b, h in manifest["files"]]
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "public-python-sdk-benchmark.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n")
    print("PUBLIC_PYTHON_SDK=PASS source_attestation=10/10 "
          "negative_controls=" + str(result["negative_controls"])
          + " named_consumer=Stripe-Flask-example "
          + " release_tag_mismatch=2/10 release_negatives="
          + str(result["release_negative_controls"])
          + " pyright_external=NOT_EVALUATED callback_dispatch=NOT_EVALUATED")


if __name__ == "__main__":
    main()
