#!/usr/bin/env python3
"""#92: source-only conformance of an immutable public API/DB/TypeScript consumer.

Reads upstream bytes; NEVER imports/executes upstream Python, migrations, or npm.
A source snapshot match is not a deployed API, database, or version-window PASS.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path
import re
import tomllib
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "fixtures/python-sdk/public-api-benchmark-v0.1.json"
MIGRATION_PREFIX = "backend/app/alembic/versions/"
MAX_FILE = 300_000


def require(ok: bool, code: str) -> None:
    if not ok:
        raise RuntimeError(code)


def git_blob(raw: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()


def request_bytes(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "codeQA-public-source-audit/0.1",
                                               "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=30) as response:
        require(response.status == 200, "UPSTREAM_HTTP_STATUS")
        require(response.geturl() == url, "UPSTREAM_REDIRECT_REJECTED")
        raw = response.read(MAX_FILE + 1_000_000)
    require(len(raw) <= MAX_FILE + 900_000, "UPSTREAM_RESPONSE_OVERSIZE")
    return raw


def fetch_pinned(manifest: dict) -> tuple[dict[str, bytes], dict[str, str]]:
    repo = manifest["benchmark"]
    commit = manifest["commit"]
    require(re.fullmatch(r"[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+", repo) is not None,
            "INVALID_UPSTREAM_REPOSITORY")
    require(re.fullmatch(r"[0-9a-f]{40}", commit) is not None,
            "INVALID_UPSTREAM_COMMIT")
    commit_obj = json.loads(request_bytes(
        "https://api.github.com/repos/" + repo + "/git/commits/" + commit))
    require(commit_obj.get("sha") == commit
            and commit_obj.get("tree", {}).get("sha") == manifest["tree"],
            "UPSTREAM_COMMIT_TREE_MISMATCH")
    tree = json.loads(request_bytes(
        "https://api.github.com/repos/" + repo + "/git/trees/"
        + manifest["tree"] + "?recursive=1"))
    require(tree.get("sha") == manifest["tree"] and tree.get("truncated") is False,
            "UPSTREAM_TREE_INCOMPLETE")
    entries = {e["path"]: e["sha"] for e in tree["tree"] if e["type"] == "blob"}
    sources = {}
    for path, _, _ in manifest["files"]:
        require(re.fullmatch(r"[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*", path) is not None,
                "UNSAFE_UPSTREAM_PATH")
        sources[path] = request_bytes(
            "https://raw.githubusercontent.com/" + repo + "/" + commit + "/" + path)
    return sources, entries


def attest(manifest: dict, sources: dict[str, bytes], tree: dict[str, str]) -> None:
    require(manifest["schema_version"] == "0.1"
            and manifest["scope"] == "PINNED_PUBLIC_SOURCE_ONLY"
            and manifest["benchmark"] == "fastapi/full-stack-fastapi-template"
            and manifest["commit"] == "b1125d8839482cb7bbae603ddc6d0081bf87532e"
            and manifest["tree"] == "94de969c70c4d283e7a57eb0795cea9a8d7813ef",
            "BENCHMARK_SELECTION_DRIFT")
    entries = manifest["files"]
    require(all(isinstance(x, list) and len(x) == 3 for x in entries),
            "MALFORMED_FILE_MANIFEST")
    paths = [x[0] for x in entries]
    require(len(set(paths)) == len(paths) and set(paths) == set(sources),
            "SOURCE_SET_INCOMPLETE")
    require(set(paths).issubset(tree), "TREE_MISSING_SELECTED_SOURCE")
    expected_migrations = {p for p in paths if p.startswith(MIGRATION_PREFIX) and p.endswith(".py")}
    actual_migrations = {p for p in tree if p.startswith(MIGRATION_PREFIX) and p.endswith(".py")}
    require(actual_migrations == expected_migrations, "MIGRATION_FILE_SET_DRIFT")
    for path, blob, sha in entries:
        raw = sources[path]
        require(0 < len(raw) <= MAX_FILE, "SOURCE_OVERSIZE_OR_EMPTY " + path)
        require(re.fullmatch(r"[0-9a-f]{40}", blob) is not None
                and re.fullmatch(r"[0-9a-f]{64}", sha) is not None,
                "INVALID_DIGEST_FORMAT")
        require(tree[path] == blob and git_blob(raw) == blob
                and hashlib.sha256(raw).hexdigest() == sha,
                "PINNED_SOURCE_HASH_MISMATCH " + path)


def literal_assign(module: ast.Module, name: str):
    values = [n.value for n in module.body if isinstance(n, ast.Assign)
              and any(isinstance(t, ast.Name) and t.id == name for t in n.targets)]
    require(len(values) == 1, "MIGRATION_METADATA_MISSING_OR_DUPLICATE " + name)
    return ast.literal_eval(values[0])


def fields_for(name: str, classes: dict[str, ast.ClassDef], stack=()) -> dict[str, bool]:
    require(name in classes and name not in stack, "MODEL_MISSING_OR_CYCLIC " + name)
    node = classes[name]
    require(not any(isinstance(x, (ast.Assign, ast.AnnAssign))
                    and any(getattr(t, "id", None) == "model_config"
                            for t in (x.targets if isinstance(x, ast.Assign) else [x.target]))
                    for x in node.body), "DYNAMIC_MODEL_CONFIG_UNSUPPORTED " + name)
    fields = {}
    for base in node.bases:
        if isinstance(base, ast.Name) and base.id in classes:
            fields.update(fields_for(base.id, classes, (*stack, name)))
    for item in node.body:
        if not isinstance(item, ast.AnnAssign) or not isinstance(item.target, ast.Name):
            continue
        field = item.target.id
        if isinstance(item.value, ast.Call):
            fn = item.value.func
            if isinstance(fn, ast.Name) and fn.id == "Relationship":
                continue
            if isinstance(fn, ast.Name) and fn.id == "Field":
                require(not any(k.arg in {"alias", "validation_alias", "serialization_alias",
                                           "alias_priority"} for k in item.value.keywords),
                        "UNREVIEWED_FIELD_ALIAS " + name + "." + field)
        if isinstance(item.value, ast.Call) and isinstance(item.value.func, ast.Name) and item.value.func.id == "Field":
            fields[field] = bool(item.value.args) or any(
                k.arg in {"default", "default_factory"} for k in item.value.keywords)
        else:
            fields[field] = item.value is not None
    return fields


def ts_fields(source: str, name: str) -> dict[str, bool]:
    match = re.search(r"(?ms)^export type " + re.escape(name)
                      + r" = \{\n(.*?)^\};", source)
    require(match is not None, "TS_CONSUMER_TYPE_MISSING " + name)
    pairs = re.findall(r"(?m)^    ([A-Za-z_]\w*)(\?)?:", match.group(1))
    require(len(pairs) == len({p[0] for p in pairs}) and bool(pairs),
            "TS_CONSUMER_FIELDS_INVALID " + name)
    return {field: bool(optional) for field, optional in pairs}


def inspect_contract(manifest: dict, sources: dict[str, bytes]) -> dict:
    def source(path: str) -> str:
        return sources[path].decode("utf-8", errors="strict")
    meta = tomllib.loads(source("backend/pyproject.toml"))["project"]
    require(meta["version"] == manifest["backend_project_version"]
            and meta["requires-python"] == manifest["backend_python_requires"],
            "UPSTREAM_DEPENDENCY_WINDOW_DRIFT")
    require(source("LICENSE").startswith("MIT License")
            and manifest["license"] == "MIT", "UPSTREAM_LICENSE_DRIFT")
    model_tree = ast.parse(source("backend/app/models.py"))
    classes = {n.name: n for n in model_tree.body if isinstance(n, ast.ClassDef)}
    ts = source("frontend/src/client/types.gen.ts")
    dto = {}
    for name, expected in manifest["dto_fields"].items():
        py = fields_for(name, classes)
        consumer = ts_fields(ts, name)
        require(set(py) == set(expected), "PUBLIC_DTO_FIELD_DRIFT " + name)
        require(py == consumer, "TS_PYTHON_DTO_MISMATCH " + name)
        dto[name] = {"fields": sorted(py), "optional": sorted(k for k, v in py.items() if v)}
    route_tree = ast.parse(source("backend/app/api/routes/users.py"))
    routes = {}
    for node in route_tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call):
                continue
            for keyword in decorator.keywords:
                if keyword.arg == "response_model" and isinstance(keyword.value, ast.Name):
                    routes[node.name] = keyword.value.id
    for method, expected in manifest["routes"].items():
        require(routes.get(method) == expected, "ROUTE_RESPONSE_MODEL_DRIFT " + method)
    sdk = source("frontend/src/client/sdk.gen.ts")
    section = re.search(r"(?s)export class UsersService \{(.*?)\n\}\n", sdk)
    require(section is not None, "TS_NAMED_CONSUMER_MISSING")
    methods = set(re.findall(r"public static (\w+)<", section.group(1)))
    require(set(manifest["ts_sdk_methods"]).issubset(methods),
            "TS_SDK_CONSUMER_METHOD_DRIFT")
    migrations = {}
    initial = {}
    for path in sources:
        if not (path.startswith(MIGRATION_PREFIX) and path.endswith(".py")):
            continue
        tree = ast.parse(source(path))
        revision = literal_assign(tree, "revision")
        predecessor = literal_assign(tree, "down_revision")
        require(re.fullmatch(r"[0-9a-f]{12}", revision) is not None
                and (predecessor is None or
                     re.fullmatch(r"[0-9a-f]{12}", predecessor) is not None),
                "MIGRATION_DYNAMIC_GRAPH_UNSUPPORTED")
        require(revision not in migrations and path.split("/")[-1].startswith(revision),
                "MIGRATION_DUPLICATE_OR_FILENAME_DRIFT")
        migrations[revision] = predecessor
        if predecessor is None:
            for call in ast.walk(tree):
                if not (isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute)
                        and call.func.attr == "create_table" and call.args
                        and isinstance(call.args[0], ast.Constant)):
                    continue
                table = call.args[0].value
                columns = [arg.args[0].value for arg in call.args[1:]
                           if isinstance(arg, ast.Call) and isinstance(arg.func, ast.Attribute)
                           and arg.func.attr == "Column" and arg.args
                           and isinstance(arg.args[0], ast.Constant)]
                initial[table] = columns
    require(migrations == manifest["migrations"], "MIGRATION_PREDECESSOR_DRIFT")
    require(len([x for x in migrations.values() if x is None]) == 1
            and len([x for x in migrations if x not in migrations.values()]) == 1,
            "MIGRATION_GRAPH_NOT_SINGLE_CHAIN")
    require({k: set(v) for k, v in initial.items()} ==
            {k: set(v) for k, v in manifest["initial_tables"].items()},
            "INITIAL_PHYSICAL_DB_SCHEMA_DRIFT")
    current = {"user": fields_for("User", classes),
               "item": fields_for("Item", classes)}
    require({k: set(v) for k, v in current.items()} ==
            {k: set(v) for k, v in manifest["current_tables"].items()},
            "CURRENT_ORM_DB_SCHEMA_DRIFT")
    require(all(set(initial[k]).issubset(current[k]) for k in initial),
            "DB_COLUMN_REMOVAL_UNREVIEWED")
    uuid_migration = source("backend/app/alembic/versions/d98dd8ec85a3_edit_replace_id_integers_in_all_models_.py")
    require("uuid_generate_v4()" in uuid_migration
            and "new_owner_id" in uuid_migration and "op.execute" in uuid_migration,
            "DATA_DEPENDENT_MIGRATION_WITNESS_MISSING")
    return {"benchmark": manifest["benchmark"], "commit": manifest["commit"],
            "consumer": manifest["consumer"], "dto": dto, "routes": manifest["routes"],
            "migration_chain": migrations, "initial_columns": initial,
            "current_columns": {k: sorted(v) for k, v in current.items()},
            "static_source_consistency": "PASS_SELECTED_FIELDS_ONLY",
            "data_dependent_uuid_migration": "NOT_EVALUATED",
            "postgresql_runtime": "NOT_EVALUATED",
            "deployed_openapi_schema": "NOT_EVALUATED",
            "historical_compatibility_window": "NOT_EVALUATED",
            "python_sdk_consumer": "NOT_EVALUATED",
            "upstream_execution": "NOT_PERFORMED"}


def negative_controls(manifest: dict, sources: dict[str, bytes], tree: dict[str, str]) -> int:
    cases = []
    def changed(path: str, old: str, new: str):
        content = sources[path].decode("utf-8")
        require(old in content, "NEGATIVE_FIXTURE_TARGET_MISSING")
        return {**sources, path: content.replace(old, new, 1).encode()}
    def check_fails(fn, label):
        try:
            fn()
        except (RuntimeError, ValueError, SyntaxError, UnicodeDecodeError):
            cases.append(label)
        else:
            raise RuntimeError("NEGATIVE_CONTROL_ACCEPTED " + label)
    check_fails(lambda: attest(manifest, changed("backend/app/models.py",
                  "class UserPublic(UserBase):", "class UserPublic(SQLModel):"), tree),
                "forged_source_bytes")
    check_fails(lambda: attest(manifest, {k: v for k, v in sources.items()
                                         if k != "frontend/src/client/sdk.gen.ts"}, tree),
                "missing_consumer_file")
    check_fails(lambda: attest(manifest, sources,
                               {k: v for k, v in tree.items()
                                if not k.endswith("fe56fa70289e_add_created_at_to_user_and_item.py")}),
                "missing_migration_tree_edge")
    check_fails(lambda: inspect_contract(manifest, changed(
                  "frontend/src/client/types.gen.ts", "export type UserPublic = {",
                  "export type UserPublic = {\n    email_alias: string;")),
                "dto_consumer_alias_drift")
    check_fails(lambda: inspect_contract(manifest, changed(
                  "backend/app/api/routes/users.py",
                  "response_model=UsersPublic", "response_model=Message")),
                "route_response_drift")
    check_fails(lambda: inspect_contract(manifest, changed(
                  "backend/app/models.py", "Field(unique=True, index=True, max_length=255)",
                  "Field(unique=True, index=True, max_length=255, serialization_alias='alias')")),
                "unreviewed_directional_alias")
    check_fails(lambda: inspect_contract(manifest, changed(
                  "backend/app/alembic/versions/9c0a54914c78_add_max_length_for_string_varchar_.py",
                  "down_revision = 'e2412789c190'", "down_revision = '000000000000'")),
                "migration_predecessor_drift")
    check_fails(lambda: inspect_contract(manifest, changed(
                  "backend/app/alembic/versions/e2412789c190_initialize_models.py",
                  'sa.Column("id", sa.Integer(), nullable=False)',
                  'sa.Column("id_renamed", sa.Integer(), nullable=False)')),
                "physical_column_drift")
    return len(cases)



def attest_history(history: dict, sources: dict[str, bytes], tree: dict[str, str]) -> None:
    require(history["scope"] == "HISTORICAL_SOURCE_SNAPSHOT_ONLY"
            and history["commit"] == "c612641e92e9c45ef6af4795fe2450bac5830369"
            and history["tree"] == "8965cb4b707bf05d0acd6703a4c0cf08add9bef2",
            "HISTORICAL_SELECTION_DRIFT")
    files = history["files"]
    require(len(files) == 10 and len({x[0] for x in files}) == 10
            and set(x[0] for x in files) == set(sources),
            "HISTORICAL_FILE_SET_DRIFT")
    migrations = {p for p in tree if p.startswith(MIGRATION_PREFIX) and p.endswith(".py")}
    require(migrations == {p for p in sources if p.startswith(MIGRATION_PREFIX) and p.endswith(".py")},
            "HISTORICAL_MIGRATION_TREE_DRIFT")
    for path, blob, digest in files:
        raw = sources[path]
        require(tree.get(path) == blob and git_blob(raw) == blob
                and hashlib.sha256(raw).hexdigest() == digest,
                "HISTORICAL_SOURCE_HASH_DRIFT " + path)


def compare_history(history: dict, old: dict[str, bytes],
                    current: dict[str, bytes]) -> dict:
    old_models = {n.name: n for n in ast.parse(old["backend/app/models.py"].decode()).body
                  if isinstance(n, ast.ClassDef)}
    new_models = {n.name: n for n in ast.parse(current["backend/app/models.py"].decode()).body
                  if isinstance(n, ast.ClassDef)}
    old_ts = old["frontend/src/client/types.gen.ts"].decode()
    new_ts = current["frontend/src/client/types.gen.ts"].decode()
    added = {}
    for name, expected in history["expected_added_optional_dto_fields"].items():
        prior, later = fields_for(name, old_models), fields_for(name, new_models)
        require(prior == ts_fields(old_ts, name)
                and later == ts_fields(new_ts, name),
                "HISTORICAL_CONSUMER_MODEL_MISMATCH " + name)
        delta = set(later) - set(prior)
        require(delta == set(expected) and not (set(prior) - set(later))
                and all(later[k] is True for k in delta)
                and all(prior[k] == later[k] for k in prior),
                "HISTORICAL_PUBLIC_DTO_DELTA_DRIFT " + name)
        added[name] = sorted(delta)
    for name in history["expected_unchanged_dto"]:
        prior, later = fields_for(name, old_models), fields_for(name, new_models)
        require(prior == later and prior == ts_fields(old_ts, name)
                and later == ts_fields(new_ts, name),
                "HISTORICAL_UNCHANGED_DTO_DRIFT " + name)
    for table, model in (("user", "User"), ("item", "Item")):
        prior, later = fields_for(model, old_models), fields_for(model, new_models)
        require(set(later) - set(prior) ==
                set(history["expected_added_orm_columns"][table])
                and not (set(prior) - set(later)),
                "HISTORICAL_ORM_COLUMN_DELTA_DRIFT " + table)
    migrations = {}
    for path, raw in old.items():
        if path.startswith(MIGRATION_PREFIX) and path.endswith(".py"):
            tree = ast.parse(raw.decode())
            revision = literal_assign(tree, "revision")
            require(revision not in migrations, "HISTORICAL_DUPLICATE_MIGRATION")
            migrations[revision] = literal_assign(tree, "down_revision")
    require(migrations == history["historical_migrations"],
            "HISTORICAL_MIGRATION_GRAPH_DRIFT")
    require(history["expected_new_migration"] not in migrations
            and history["expected_new_migration"] == "fe56fa70289e",
            "HISTORICAL_ADDED_MIGRATION_DRIFT")
    # Verify that the newer revision really declares the selected physical
    # columns; a filename/predecessor alone is not migration DDL evidence.
    migration_path = next((p for p in current
                           if p.startswith(MIGRATION_PREFIX + history["expected_new_migration"])),
                          None)
    require(migration_path is not None, "NEW_MIGRATION_SOURCE_MISSING")
    migration_tree = ast.parse(current[migration_path].decode())
    upgrade = next((n for n in migration_tree.body
                    if isinstance(n, ast.FunctionDef) and n.name == "upgrade"), None)
    require(upgrade is not None, "NEW_MIGRATION_UPGRADE_MISSING")
    physical_additions = set()
    for node in ast.walk(upgrade):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == "add_column" and len(node.args) == 2
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[1], ast.Call)
                and len(node.args[1].args) >= 1
                and isinstance(node.args[1].args[0], ast.Constant)):
            continue
        physical_additions.add((node.args[0].value, node.args[1].args[0].value))
    require(physical_additions == {("user", "created_at"), ("item", "created_at")},
            "HISTORICAL_MIGRATION_PHYSICAL_DDL_DRIFT")
    old_project = tomllib.loads(old["backend/pyproject.toml"].decode())["project"]
    new_project = tomllib.loads(current["backend/pyproject.toml"].decode())["project"]
    require(old_project["version"] == new_project["version"] == "0.1.0"
            and old_project["requires-python"] == history["backend_python_requires"]
            and old_project["requires-python"] != new_project["requires-python"],
            "HISTORICAL_DEPENDENCY_WINDOW_DRIFT")
    return {"older_commit": history["commit"],
            "newer_commit": "b1125d8839482cb7bbae603ddc6d0081bf87532e",
            "consumer": "TypeScript generated client in both exact source trees",
            "added_optional_dto_fields": added,
            "added_orm_columns": history["expected_added_orm_columns"],
            "added_migration": history["expected_new_migration"],
            "project_version_both_snapshots": old_project["version"],
            "python_requirement_old": old_project["requires-python"],
            "python_requirement_new": new_project["requires-python"],
            "selected_source_delta": "PASS_ATTESTED_SNAPSHOT_PAIR_ONLY",
            "published_release_compatibility_window": "NOT_EVALUATED",
            "data_migration_and_deployment": "NOT_EVALUATED"}


def history_negative_controls(history: dict, old: dict[str, bytes],
                              current: dict[str, bytes], tree: dict[str, str]) -> int:
    checks = []
    def reject(label: str, call) -> None:
        try:
            call()
        except (RuntimeError, ValueError, SyntaxError):
            checks.append(label)
        else:
            raise RuntimeError("HISTORY_NEGATIVE_ACCEPTED " + label)
    def replace(path: str, before: str, after: str) -> dict[str, bytes]:
        source = old[path].decode()
        require(before in source, "HISTORY_NEGATIVE_TARGET_MISSING")
        return {**old, path: source.replace(before, after, 1).encode()}
    newer_path = next(p for p in current if p.startswith(
        MIGRATION_PREFIX + history["expected_new_migration"]))
    newer = current[newer_path].decode()
    require("sa.Column('created_at'" in newer, "HISTORY_NEGATIVE_DDL_TARGET_MISSING")
    forged_current = {**current, newer_path: newer.replace(
        "sa.Column('created_at'", "sa.Column('renamed_at'", 1).encode()}
    reject("new_migration_physical_ddl", lambda: compare_history(
        history, old, forged_current))
    reject("historical_digest", lambda: attest_history(history, replace(
        "backend/app/models.py", "class UserPublic", "class OtherPublic"), tree))
    reject("historical_ts_alias", lambda: compare_history(history, replace(
        "frontend/src/client/types.gen.ts", "export type UserPublic = {",
        "export type UserPublic = {\n    alias_added?: string;"), current))
    reject("historical_model_field", lambda: compare_history(history, replace(
        "backend/app/models.py", "class UserPublic(UserBase):",
        "class UserPublic(UserBase):\n    added: str = None"), current))
    forged = {**history, "historical_migrations":
              {**history["historical_migrations"], "1a31ce608336": None}}
    reject("missing_migration_edge", lambda: compare_history(forged, old, current))
    forged = {**history, "expected_added_optional_dto_fields":
              {**history["expected_added_optional_dto_fields"],
               "UserPublic": ["renamed_field"]}}
    reject("forged_compatibility_delta", lambda: compare_history(forged, old, current))
    return len(checks)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    sources, tree = fetch_pinned(manifest)
    attest(manifest, sources, tree)
    report = inspect_contract(manifest, sources)
    history_path = ROOT / "fixtures/python-sdk/public-api-history-v0.1.json"
    history = json.loads(history_path.read_bytes())
    older_sources, older_tree = fetch_pinned(history)
    attest_history(history, older_sources, older_tree)
    history_report = compare_history(history, older_sources, sources)
    history_report["negative_controls"] = history_negative_controls(
        history, older_sources, sources, older_tree)
    history_report["manifest_sha256"] = hashlib.sha256(history_path.read_bytes()).hexdigest()
    report["historical_pair"] = history_report
    report["source_files"] = [{"path": path, "git_blob": blob, "sha256": digest}
                              for path, blob, digest in manifest["files"]]
    report["negative_controls"] = negative_controls(manifest, sources, tree)
    report["manifest_sha256"] = hashlib.sha256(MANIFEST.read_bytes()).hexdigest()
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "public-api-history.json").write_text(
        json.dumps(history_report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (args.output / "public-api-benchmark.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("PUBLIC_API_HISTORY=PASS older_files=10/10 added_optional="
          + repr(history_report["added_optional_dto_fields"])
          + " negative_controls=" + str(history_report["negative_controls"])
          + " deployed_version_window=NOT_EVALUATED")
    print("PUBLIC_API_BENCHMARK=PASS source_attestation=11/11 "
          "negative_controls=" + str(report["negative_controls"])
          + " consumer=TypeScript compatibility=PINNED_SOURCE_ONLY "
          "migration_runtime=NOT_EVALUATED")


if __name__ == "__main__":
    main()
