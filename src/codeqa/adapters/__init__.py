"""Language adapters convert source code into language-independent CCG facts."""
from .python import adapt_python_sources
from .python_dependencies import extract_python_dependencies
from .python_snapshot import PythonAnalysisCache

__all__ = ["adapt_python_sources", "extract_python_dependencies", "PythonAnalysisCache"]
