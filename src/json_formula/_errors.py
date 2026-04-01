"""Internal helpers for creating JSON Formula exceptions."""

from __future__ import annotations

from .exceptions import EvaluationError, FunctionError, SyntaxError, TypeError


def type_error(message: str) -> TypeError:
    return TypeError(message)


def syntax_error(message: str) -> SyntaxError:
    return SyntaxError(message)


def function_error(message: str) -> FunctionError:
    return FunctionError(message)


def evaluation_error(message: str) -> EvaluationError:
    return EvaluationError(message)
