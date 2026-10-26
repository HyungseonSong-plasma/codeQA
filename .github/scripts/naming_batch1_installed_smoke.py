#!/usr/bin/env python3
"""Read-only #91 installed-distribution contract smoke.

Executed by the existing isolated wheel/sdist jobs with python -I from
outside the checkout. Checks current packaged API only, not external clients.
"""
from __future__ import annotations

from dataclasses import FrozenInstanceError, asdict, fields
from hashlib import sha256
import inspect
from pathlib import Path

import codeqa.core.naming_glossary as module


def main() -> None:
    location = Path(module.__file__).resolve()
    if "site-packages" not in location.parts:
        raise AssertionError("codeqa module not imported from isolated installation")
    if module.tokenize_identifier("readNodeID") != ("read", "node", "id"):
        raise AssertionError("tokenization contract changed")
    if module.tokenize_identifier("time_step") != ("time", "step"):
        raise AssertionError("canonical tokenization contract changed")
    if module.tokenize_identifier("nodeid") != ("nodeid",):
        raise AssertionError("explicit alias tokenization contract changed")
    try:
        module.tokenize_identifier(5)
    except module.NamingGlossaryError:
        pass
    else:
        raise AssertionError("invalid input must raise NamingGlossaryError")

    if [f.name for f in fields(module.GlossaryTerm)] != [
        "canonical", "aliases", "kinds"
    ]:
        raise AssertionError("dataclass field layout changed")
    if list(inspect.signature(module.GlossaryTerm).parameters) != [
        "canonical", "aliases", "kinds"
    ]:
        raise AssertionError("constructor signature changed")
    term = module.GlossaryTerm(
        canonical="time_step", aliases=("timestep",), kinds=("parameter",)
    )
    if asdict(term)["canonical"] != "time_step":
        raise AssertionError("serialized canonical key missing")
    try:
        term.canonical = "other"
    except FrozenInstanceError:
        pass
    else:
        raise AssertionError("dataclass immutability changed")

    profile_input = {
        "schema_version": "0.1",
        "profile_id": "codeqa.naming.glossary.v0.1",
        "include_prefixes": ["src/"],
        "terms": [
            {"canonical": "time_step",
             "aliases": ["timestep"], "kinds": ["parameter"]},
        ],
    }
    if not isinstance(
        module.NamingGlossaryProfile.__dict__["from_mapping"], classmethod
    ):
        raise AssertionError("classmethod binding changed")
    profile = module.NamingGlossaryProfile.from_mapping(profile_input)
    if profile.terms[0].canonical != "time_step":
        raise AssertionError("factory return contract changed")
    first = profile.fingerprint()
    if first != module.NamingGlossaryProfile.from_mapping(profile_input).fingerprint():
        raise AssertionError("profile fingerprint instability")
    if len(first) != 64 or not all(c in "0123456789abcdef" for c in first):
        raise AssertionError("profile fingerprint invalid")
    invalid = dict(profile_input, unexpected="key")
    try:
        module.NamingGlossaryProfile.from_mapping(invalid)
    except module.NamingGlossaryError:
        pass
    else:
        raise AssertionError("unknown input keys must be rejected")
    print(
        "NAMING_BATCH1_INSTALLED_CONTRACT=PASS",
        "package=" + str(location),
        "tokenizer=PASS",
        "dataclass=PASS",
        "from_mapping=PASS",
        "external_consumers=NOT_EVALUATED",
        "auto_rename=NOT_AUTHORIZED",
    )


if __name__ == "__main__":
    main()
