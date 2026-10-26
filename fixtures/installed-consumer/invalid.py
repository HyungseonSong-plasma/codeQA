"""Installed-wheel typechecker negative controls: must be rejected by real Pyright."""
from codeqa.pipeline.analysis_request import (
    AnalysisOptions, AnalysisRequest, analyze_python_request,
)

# reportArgumentType: tuple element must be a string.
bad_options = AnalysisOptions(changed_paths=(1,))

# reportArgumentType: source mapping keys must be strings.
bad_request = AnalysisRequest(
    sources={1: "def x(): pass"},
    snapshot_id="controlled-negative",
    ccg_schema={},
    mechanical_profile={},
)

# reportArgumentType: the consumer entrypoint requires a typed request.
bad_response = analyze_python_request("not an AnalysisRequest")

# reportAssignmentType: no implicit conversion from string to AnalysisOptions.
bad_assignment: AnalysisOptions = "not an AnalysisOptions"
