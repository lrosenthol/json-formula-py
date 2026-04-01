"""Exception hierarchy for JSON Formula."""

from __future__ import annotations


class JsonFormulaError(Exception):
    """Base exception for JSON Formula errors."""


class SyntaxError(JsonFormulaError):
    """Expression parsing failed."""


class FunctionError(JsonFormulaError):
    """Function resolution or arity validation failed."""


class EvaluationError(JsonFormulaError):
    """Evaluation failed at runtime."""


class TypeError(JsonFormulaError):
    """Type coercion or type compatibility failed."""
