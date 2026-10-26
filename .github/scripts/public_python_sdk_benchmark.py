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
from pathlib import Path
import tomllib

from public_api_benchmark import fetch_pinned, git_blob, require

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "fixtures/python-sdk/public-python-sdk-benchmark-v0.1.json"


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
                    {a.name for a in n.names}) for n in ast.walk(exports)),
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


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    manifest = json.loads(MANIFEST.read_bytes())
    sources, tree = fetch_pinned(manifest)
    attest(manifest, sources, tree)
    result = inspect(manifest, sources)
    result["negative_controls"] = negative_controls(manifest, sources, tree)
    result["manifest_sha256"] = hashlib.sha256(MANIFEST.read_bytes()).hexdigest()
    result["source_files"] = [{"path": p, "git_blob": b, "sha256": h}
                              for p, b, h in manifest["files"]]
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "public-python-sdk-benchmark.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n")
    print("PUBLIC_PYTHON_SDK=PASS source_attestation=10/10 "
          "negative_controls=" + str(result["negative_controls"])
          + " named_consumer=Stripe-Flask-example "
          "pyright_external=NOT_EVALUATED callback_dispatch=NOT_EVALUATED")


if __name__ == "__main__":
    main()
