"""Compose internal codeQA analysis stages without central-OS orchestration."""
from .python import PythonAnalysis, analyze_python

__all__ = ["PythonAnalysis", "analyze_python"]
