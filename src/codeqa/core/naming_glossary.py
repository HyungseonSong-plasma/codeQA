"""Versioned explicit project naming glossary, not inferred semantic similarity."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict,dataclass
from hashlib import sha256
import json
import re
from typing import Any


class NamingGlossaryError(ValueError):
    pass


TOKEN=re.compile(r"(?:[A-Z]+(?=[A-Z][a-z]|\d|$)|[A-Z]?[a-z]+|[A-Z]+|\d+)")


def tokenize_identifier(name: str) -> tuple[str,...]:
    if not isinstance(name,str):
        raise NamingGlossaryError("identifier must be text")
    tokens=[]
    for segment in name.split("_"):
        if segment:
            matched=TOKEN.findall(segment)
            if "".join(matched)!=segment:
                return ()
            tokens.extend(x.lower() for x in matched)
    return tuple(tokens)


@dataclass(frozen=True,slots=True)
class GlossaryTerm:
    canonical: str
    aliases: tuple[str,...]
    kinds: tuple[str,...]


@dataclass(frozen=True,slots=True)
class NamingGlossaryProfile:
    schema_version: str
    profile_id: str
    include_prefixes: tuple[str,...]
    terms: tuple[GlossaryTerm,...]

    @classmethod
    def from_mapping(cls,value:Mapping[str,Any])->NamingGlossaryProfile:
        if not isinstance(value,Mapping) or set(value)!={
            "schema_version","profile_id","include_prefixes","terms"
        }:
            raise NamingGlossaryError("invalid project glossary profile")
        if value["schema_version"]!="0.1" or value["profile_id"]!="codeqa.naming.glossary.v0.1":
            raise NamingGlossaryError("unknown glossary profile")
        prefixes=value["include_prefixes"]
        if (not isinstance(prefixes,list) or not prefixes or
                len(set(prefixes))!=len(prefixes) or
                any(not isinstance(p,str) or not p or p.startswith("/")
                    or "\\" in p or ".." in p.split("/") or
                    not p.endswith("/") for p in prefixes)):
            raise NamingGlossaryError("invalid glossary path scopes")
        values=value["terms"]
        if not isinstance(values,list) or not values:
            raise NamingGlossaryError("a non-empty declared domain glossary is required")
        terms=[]
        ownership={}
        allowed={"module","class","function","method","parameter","field","import_alias"}
        for item in values:
            if not isinstance(item,Mapping) or set(item)!={"canonical","aliases","kinds"}:
                raise NamingGlossaryError("invalid term policy")
            canonical=item["canonical"]
            aliases=item["aliases"]
            kinds=item["kinds"]
            if (not isinstance(canonical,str) or
                    not re.fullmatch("[a-z][a-z0-9]*(?:_[a-z0-9]+)*",canonical)
                    or not isinstance(aliases,list) or not aliases or
                    len(set(aliases))!=len(aliases) or
                    not isinstance(kinds,list) or not kinds or
                    len(set(kinds))!=len(kinds) or
                    not set(kinds)<=allowed):
                raise NamingGlossaryError("invalid canonical spelling/aliases/kinds")
            terms.append(GlossaryTerm(canonical,tuple(sorted(aliases)),tuple(sorted(kinds))))
            for phrase in [canonical,*aliases]:
                if (not isinstance(phrase,str)
                        or not re.fullmatch("[A-Za-z][A-Za-z0-9_]*",phrase)):
                    raise NamingGlossaryError("unsupported glossary spelling")
                tokens=tokenize_identifier(phrase)
                if not tokens:
                    raise NamingGlossaryError("glossary phrase cannot be tokenized")
                for k in kinds:
                    key=(k,tokens)
                    if key in ownership:
                        raise NamingGlossaryError("overlapping/ambiguous canonical or alias term")
                    ownership[key]=canonical
        keys=[x.canonical for x in terms]
        if len(set(keys))!=len(keys):
            raise NamingGlossaryError("duplicate canonical term")
        return cls("0.1",value["profile_id"],tuple(sorted(prefixes)),
                   tuple(sorted(terms,key=lambda x:x.canonical)))

    def fingerprint(self)->str:
        value=asdict(self)
        return sha256(json.dumps(value,sort_keys=True,separators=(",",":")).encode()).hexdigest()
