"""Installed-wheel consumer type witness, not an external public SDK baseline."""
from collections.abc import Mapping

from codeqa.pipeline.analysis_request import (
    AnalysisOptions, AnalysisRequest, AnalysisResponse, analyze_python_request,
)


def build_request() -> AnalysisRequest:
    return AnalysisRequest(
        sources={"sample.py": "def hello():\n    return 1\n"},
        snapshot_id="controlled-installed-consumer",
        ccg_schema={},
        mechanical_profile={},
        options=AnalysisOptions(changed_paths=("sample.py",)),
    )


def use_response(request: AnalysisRequest) -> Mapping[str, str]:
    response: AnalysisResponse = analyze_python_request(request)
    return response.companion_states
