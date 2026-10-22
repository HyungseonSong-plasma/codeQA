"""Language adapters convert source code into language-independent CCG facts."""
from .python import adapt_python_sources

__all__ = ["adapt_python_sources"]
