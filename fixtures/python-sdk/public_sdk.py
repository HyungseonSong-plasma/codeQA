"""Controlled re-export of an actually installed Pydantic SDK type.

This is NOT an independently identified production SDK or consumer contract.
"""
from pydantic import BaseModel as ExportedModel

__all__ = ["ExportedModel"]
