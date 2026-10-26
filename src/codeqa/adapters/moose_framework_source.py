"""Pinned upstream MOOSE *source identity* witness, not framework ABI/DSL proof.

No framework execution or production renaming is authorized by this module.
"""
from __future__ import annotations

from hashlib import sha1, sha256
import re
from typing import Any, Mapping


class MooseFrameworkSourceError(ValueError):
    """Framework source bytes, dependency lock or provenance are unverified."""


FRAMEWORK_REPO = "idaholab/moose"
APPLICATION_REPO = "HyungseonSong-plasma/moose-test-repo"
REQUIRED_FILES = frozenset({
    "framework/include/base/MooseApp.h",
    "framework/include/utils/InputParameters.h",
    "framework/src/parser/Parser.C",
    "framework/include/parser/MooseSyntax.h",
    "framework/src/parser/Syntax.C",
    "framework/contrib/hit/src/hit/lex.cc",
    "framework/contrib/hit/src/hit/parse.cc",
    "framework/contrib/hit/include/hit/parse.h",
})


def git_blob_sha(data: bytes) -> str:
    """Compute Git SHA-1 object identity for exact bytes, not semantic equivalence."""
    if not isinstance(data, bytes):
        raise MooseFrameworkSourceError("Git blob must contain bytes")
    return sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()


def verify_framework_source_lock(
    lock: Mapping[str, Any], dependency_lock: str,
    files: Mapping[str, bytes], *, application_revision: str,
) -> dict[str, Any]:
    """Reject stale/partial/forged source identity without claiming ABI support."""
    if not isinstance(lock, Mapping) or set(lock) != {
        "schema_version", "framework_repository", "framework_revision",
        "application_repository", "application_revision", "files",
        "authority",
    }:
        raise MooseFrameworkSourceError("invalid framework source lock")
    if (lock["schema_version"] != "0.1"
            or lock["framework_repository"] != FRAMEWORK_REPO
            or lock["application_repository"] != APPLICATION_REPO
            or lock["authority"] != "PINNED_SOURCE_IDENTITY_ONLY"):
        raise MooseFrameworkSourceError("unapproved framework source authority")
    revision = lock["framework_revision"]
    if (not isinstance(revision, str) or not re.fullmatch(r"[0-9a-f]{40}", revision)
            or not isinstance(application_revision, str)
            or not re.fullmatch(r"[0-9a-f]{40}", application_revision)
            or lock["application_revision"] != application_revision):
        raise MooseFrameworkSourceError("unverified framework/application revision")
    if not isinstance(dependency_lock, str):
        raise MooseFrameworkSourceError("missing application dependency lock")
    # Check *every* MOOSE assignment candidate, including whitespace,
    # shell-style export, malformed and branch-valued duplicates. Do not
    # mistake a commented example for an active assignment.
    assignments = [line for line in dependency_lock.splitlines()
                   if re.match(r"^\s*(?:export\s+)?MOOSE\s*=", line)]
    if assignments != ["MOOSE=" + revision]:
        raise MooseFrameworkSourceError("framework revision differs from application lock")
    expected = lock["files"]
    if (not isinstance(expected, dict) or set(expected) != REQUIRED_FILES
            or not isinstance(files, Mapping) or set(files) != REQUIRED_FILES):
        raise MooseFrameworkSourceError("partial, extra or unsupported framework source set")
    receipts = {}
    for path in sorted(REQUIRED_FILES):
        value, data = expected[path], files[path]
        if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{40}", value):
            raise MooseFrameworkSourceError("invalid pinned framework Git blob")
        if git_blob_sha(data) != value:
            raise MooseFrameworkSourceError("stale or altered framework source: " + path)
        receipts[path] = {"git_blob_sha1": value, "sha256": sha256(data).hexdigest()}
    return {
        "schema_version": "0.1",
        "framework_repository": FRAMEWORK_REPO,
        "framework_revision": revision,
        "application_repository": APPLICATION_REPO,
        "application_revision": application_revision,
        "files": receipts,
        "authority": "PINNED_SOURCE_IDENTITY_ONLY",
        "framework_release": "NOT_EVALUATED",
        "input_dsl_grammar": "NOT_EVALUATED",
        "reserved_vs_customizable_names": "NOT_EVALUATED",
        "build_abi_and_runtime": "NOT_EVALUATED",
    }
