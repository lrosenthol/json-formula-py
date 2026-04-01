"""Runtime wrapper for parsing and evaluating formulas."""

from __future__ import annotations

from typing import Any

from ._errors import evaluation_error, function_error, type_error
from .functions import build_functions
from .interpreter import TreeInterpreter
from .match_type import get_type, is_array_type, match_type
from .parser import Parser
from .utils import get_value_of, is_object


def default_string_to_number(value: str) -> float:
    try:
        return float(value)
    except Exception:
        return 0.0


def get_to_number(string_to_number):
    def convert(value: Any) -> float:
        candidate = get_value_of(value)
        if candidate is None:
            return 0.0
        if isinstance(candidate, list):
            raise type_error("Failed to convert array to number")
        if isinstance(candidate, (int, float)) and not isinstance(candidate, bool):
            return candidate
        if isinstance(candidate, str):
            return string_to_number(candidate)
        if isinstance(candidate, bool):
            return 1.0 if candidate else 0.0
        raise type_error("Failed to convert object to number")

    return convert


def to_string(value: Any) -> str:
    value = get_value_of(value)
    if value is None:
        return ""
    if is_array_type(value):
        raise type_error("Failed to convert array to string")
    if is_object(value):
        raise type_error("Failed to convert object to string")
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


class Runtime:
    def __init__(self, debug: list[str], to_number, custom_functions: dict[str, Any] | None = None) -> None:
        self.debug = debug
        self.to_number = to_number
        self.function_table = build_functions(
            self,
            is_object,
            to_number,
            get_type,
            is_array_type,
            get_value_of,
            to_string,
            debug,
        )
        for name, func in (custom_functions or {}).items():
            self.function_table[name] = func

    def call_function(self, name: str, resolved_args: list[Any], data: Any, interpreter, resolved: bool = True) -> Any:
        if name not in self.function_table:
            raise function_error(f"No such function: {name}()")
        entry = self.function_table[name]
        self._validate_args(name, resolved_args, entry["signature"], resolved)
        return entry["func"](resolved_args, data, interpreter)

    def _validate_args(self, name: str, args: list[Any], signature: list[dict[str, Any]], resolved: bool) -> None:
        if len(signature) == 0 and args:
            raise function_error(f"{name}() does not accept parameters")
        if len(signature) == 0:
            return
        required = len([item for item in signature if not item.get("optional")])
        last = signature[-1]
        if last.get("variadic"):
            if len(args) < len(signature) and not last.get("optional"):
                raise function_error(f"{name}() takes at least {len(signature)} arguments but received {len(args)}")
        elif len(args) < required or len(args) > len(signature):
            raise function_error(f"{name}() takes {len(signature)} arguments but received {len(args)}")
        if not resolved:
            return
        limit = len(args) if last.get("variadic") else min(len(signature), len(args))
        for index in range(limit):
            current = signature[index]["types"] if index < len(signature) else signature[-1]["types"]
            args[index] = match_type(current, args[index], name, self.to_number, to_string)


class Formula:
    def __init__(self, debug: list[str], custom_functions: dict[str, Any] | None = None, string_to_number_fn=None) -> None:
        self.debug = debug
        self.to_number = get_to_number(string_to_number_fn or default_string_to_number)
        self.runtime = Runtime(debug, self.to_number, custom_functions)

    def compile(self, expression: str, allowed_global_names: list[str] | None = None) -> dict[str, Any]:
        parser = Parser(allowed_global_names or [])
        return parser.parse(expression, self.debug)

    def search(self, node: dict[str, Any], data: Any, globals_: dict[str, Any] | None = None, language: str = "en-US") -> Any:
        self.runtime.interpreter = TreeInterpreter(self.runtime, globals_ or {}, self.to_number, to_string, self.debug, language)
        try:
            return self.runtime.interpreter.search(node, data)
        except Exception as exc:
            self.debug.append(str(exc))
            if exc.__class__.__name__ == "Exception":
                raise evaluation_error(str(exc)) from exc
            raise
