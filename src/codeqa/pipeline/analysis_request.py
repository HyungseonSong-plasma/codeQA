"""Optional versioned Python AnalysisRequest wrapper (#123).

Existing analyze_python defaults and frozen QA Result v0.1 are untouched.
Naming, Formal and external Gate remain separate, explicit trust domains.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from hashlib import sha256
import json
from typing import Any

from codeqa.adapters.python_snapshot import PythonAnalysisCache
from codeqa.pipeline.python import PythonAnalysis, analyze_python


class AnalysisRequestError(ValueError):
    """An optional request would imply unsupported or ambiguous execution."""


@dataclass(frozen=True, slots=True)
class AnalysisOptions:
    version: str = "0.1"
    changed_paths: tuple[str, ...] = ()
    semantic_policy: Mapping[str, Any] | None = None
    behavior_policy: Mapping[str, Any] | None = None
    naming: bool = False
    formal: bool = False
    external_gate: bool = False

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "AnalysisOptions":
        if not isinstance(value, Mapping):
            raise AnalysisRequestError("options must be a mapping")
        allowed = set(cls.__dataclass_fields__)
        if set(value) - allowed:
            raise AnalysisRequestError("unknown analysis options")
        paths = value.get("changed_paths", ())
        if not isinstance(paths, (tuple, list)) or any(
            not isinstance(p, str) or not p or p.startswith("/")
            or "\\" in p or any(ord(c) < 32 or ord(c) == 127 for c in p)
            or any(part in ("", ".", "..") for part in p.split("/"))
            for p in paths
        ) or len(set(paths)) != len(paths):
            raise AnalysisRequestError("invalid or duplicate changed paths")
        opts = cls(**{**value, "changed_paths": tuple(paths)})
        opts.validate()
        return opts

    def validate(self) -> None:
        if self.version != "0.1":
            raise AnalysisRequestError("unknown analysis request version")
        for authority in ("naming", "formal", "external_gate"):
            if type(getattr(self, authority)) is not bool:
                raise AnalysisRequestError("authority option must be an explicit Boolean")
        if self.naming or self.formal or self.external_gate:
            raise AnalysisRequestError(
                "Naming, Formal and external Gate require separate opt-in APIs and evidence"
            )
        for policy in (self.semantic_policy, self.behavior_policy):
            if policy is not None and not isinstance(policy, Mapping):
                raise AnalysisRequestError("optional policy must be a mapping")
        if (not isinstance(self.changed_paths, tuple)
                or len(set(self.changed_paths)) != len(self.changed_paths)
                or any(not isinstance(p, str) or not p or p.startswith("/")
                       or "\\" in p or any(ord(c) < 32 or ord(c) == 127 for c in p)
                       or any(part in ("", ".", "..") for part in p.split("/"))
                       for p in self.changed_paths)):
            raise AnalysisRequestError("invalid changed paths")
        self.fingerprint()

    def fingerprint(self) -> str:
        try:
            payload = json.dumps({
                "version": self.version,
                "changed_paths": self.changed_paths,
                "semantic_policy": self.semantic_policy,
                "behavior_policy": self.behavior_policy,
                "naming": self.naming,
                "formal": self.formal,
                "external_gate": self.external_gate,
            }, sort_keys=True, separators=(",", ":"), allow_nan=False)
        except (TypeError, ValueError) as exc:
            raise AnalysisRequestError("non-JSON or non-finite analysis options") from exc
        return sha256(payload.encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class AnalysisRequest:
    sources: Mapping[str, str]
    snapshot_id: str
    ccg_schema: Mapping[str, Any]
    mechanical_profile: Mapping[str, Any]
    options: AnalysisOptions = field(default_factory=AnalysisOptions)


@dataclass(frozen=True, slots=True)
class AnalysisResponse:
    analysis: PythonAnalysis
    options_fingerprint: str
    companion_states: Mapping[str, str]
    profile_fingerprints: Mapping[str, str] = field(default_factory=dict)
    schema_version: str = "0.1"

    def summary_document(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "options_fingerprint": self.options_fingerprint,
            "profile_fingerprints": dict(sorted(self.profile_fingerprints.items())),
            "companion_states": dict(self.companion_states),
            "analysis": self.analysis.summary_document(),
            "interpretation": "OPTIONAL_PYTHON_PIPELINE_NOT_UNIVERSAL_QA_RESULT",
        }


def analyze_python_request(
    request: AnalysisRequest, *, cache: PythonAnalysisCache | None = None,
) -> AnalysisResponse:
    """Compose only explicitly selected, already implemented Python stages."""
    if not isinstance(request, AnalysisRequest) or not isinstance(request.options, AnalysisOptions):
        raise TypeError("typed AnalysisRequest and AnalysisOptions required")
    opts = request.options
    opts.validate()
    if not isinstance(request.snapshot_id, str) or not request.snapshot_id:
        raise AnalysisRequestError("immutable snapshot identity required")
    analysis = analyze_python(
        request.sources, snapshot_id=request.snapshot_id,
        ccg_schema=request.ccg_schema,
        mechanical_profile=request.mechanical_profile,
        cache=cache,
        changed_paths=opts.changed_paths or None,
        semantic_policy=opts.semantic_policy,
        behavior_policy=opts.behavior_policy,
    )
    return AnalysisResponse(
        analysis=analysis,
        options_fingerprint=opts.fingerprint(),
        profile_fingerprints={"ccg_schema": sha256(json.dumps(request.ccg_schema, sort_keys=True).encode()).hexdigest(), "mechanical_profile": sha256(json.dumps(request.mechanical_profile, sort_keys=True).encode()).hexdigest()},
        companion_states={
            "impact": "EXECUTED" if analysis.impact is not None else "NOT_REQUESTED",
            "semantic_architecture": (
                "EXECUTED" if analysis.semantic_architecture is not None else "NOT_REQUESTED"
            ),
            "responsibility_behavior": (
                "EXECUTED" if analysis.responsibility_behavior is not None else "NOT_REQUESTED"
            ),
            "naming": "NOT_REQUESTED",
            "formal": "NOT_REQUESTED",
            "external_gate": "NOT_REQUESTED",
        },
    )
