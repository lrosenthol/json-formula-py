# Copyright 2026 Adobe. All rights reserved.
# This file is licensed to you under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License. You may obtain a copy
# of the License at http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software distributed under
# the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR REPRESENTATIONS
# OF ANY KIND, either express or implied. See the License for the specific language
# governing permissions and limitations under the License.

"""AST interpreter for JSON Formula."""

from __future__ import annotations

import math
from typing import Any

from ._errors import evaluation_error, type_error
from .data_types import TYPE_ARRAY, TYPE_ARRAY_STRING, TYPE_NUMBER, TYPE_STRING
from .match_type import get_type, get_type_name, is_array_type, match_type
from .tokens import TOK_CURRENT, TOK_EXPREF, TOK_FLATTEN, TOK_GLOBAL, TOK_PIPE
from .utils import debug_available, get_property, get_value_of, is_array, is_object, strict_deep_equal, to_boolean


def _balance_array_operands(left: Any, right: Any) -> tuple[Any, Any]:
    if is_array(left) and is_array(right):
        max_len = max(len(left), len(right))
        return left + [None] * (max_len - len(left)), right + [None] * (max_len - len(right))
    return left, right


class TreeInterpreter:
    def __init__(self, runtime, globals_: dict[str, Any], to_number, to_string, debug: list[str], language: str) -> None:
        self.runtime = runtime
        self.globals = globals_
        self.to_number = to_number
        self.to_string = to_string
        self.debug = debug
        self.language = language
        self.debug_chain_start: str | None = None

    def search(self, node: dict[str, Any], value: Any) -> Any:
        return self.visit(node, value)

    def field(self, node: dict[str, Any], value: Any) -> Any:
        if value is not None and (is_object(value) or is_array(value) or hasattr(value, "__dict__")):
            field = get_property(value, node["name"])
            if field is None:
                debug_available(self.debug, value, node["name"], self.debug_chain_start)
                return None
            return field
        debug_available(self.debug, value, node["name"], self.debug_chain_start)
        return None

    def visit(self, node: dict[str, Any], value: Any = None) -> Any:
        node_type = node["type"]
        if node_type in {"Identifier", "QuotedIdentifier"}:
            return self.field(node, value)
        if node_type == "ChainedExpression":
            result = self.visit(node["children"][0], value)
            self.debug_chain_start = node["children"][0].get("name")
            for child in node["children"][1:]:
                result = self.visit(child, result)
                if result is None:
                    return None
            return result
        if node_type == "BracketExpression":
            return self.visit(node["children"][1], self.visit(node["children"][0], value))
        if node_type == "Index":
            if is_array(value):
                index = node["value"]["value"]
                if index < 0:
                    index = len(value) + index
                if 0 <= index < len(value):
                    return value[index]
                self.debug.append(f"Index: {index} out of range for array size: {len(value)}")
                return None
            self.debug.append("Left side of index expression must be an array")
            self.debug.append(f"Did you intend a single-element array? if so, use a JSON literal: `[{node['value']['value']}]`")
            return None
        if node_type == "Slice":
            if not is_array(value):
                self.debug.append("Slices apply to arrays only")
                return None
            start, stop, step = self.compute_slice_params(
                len(value), [None if item is None else item["value"] for item in node["children"]]
            )
            result: list[Any] = []
            if step > 0:
                index = start
                while index < stop:
                    result.append(value[index])
                    index += step
            else:
                index = start
                while index > stop:
                    result.append(value[index])
                    index += step
            return result
        if node_type == "Projection":
            base = self.visit(node["children"][0], value)
            if not is_array(base):
                if node.get("debug") == "Wildcard":
                    self.debug.append("Bracketed wildcards apply to arrays only")
                return None
            return [self.visit(node["children"][1], item) for item in base]
        if node_type == "ValueProjection":
            projection = self.visit(node["children"][0], value)
            if not is_object(get_value_of(projection)):
                self.debug.append("Chained wildcards apply to objects only")
                return None
            return [self.visit(node["children"][1], item) for item in get_value_of(projection).values()]
        if node_type == "FilterProjection":
            base = self.visit(node["children"][0], value)
            if not is_array(base):
                self.debug.append("Filter expressions apply to arrays only")
                return None
            filtered = [item for item in base if to_boolean(self.visit(node["children"][2], item))]
            return [self.visit(node["children"][1], item) for item in filtered]
        if node_type == "Comparator":
            first = get_value_of(self.visit(node["children"][0], value))
            second = get_value_of(self.visit(node["children"][1], value))
            if node["value"] == "==":
                return strict_deep_equal(first, second)
            if node["value"] == "!=":
                return not strict_deep_equal(first, second)
            if is_object(first) or is_array(first):
                self.debug.append(f"Cannot use comparators with {get_type_name(first)}")
                return False
            if is_object(second) or is_array(second):
                self.debug.append(f"Cannot use comparators with {get_type_name(second)}")
                return False
            if get_type(first) == TYPE_STRING and get_type(second) == TYPE_STRING:
                pass
            else:
                try:
                    first = self.to_number(first)
                    second = self.to_number(second)
                except Exception:
                    return False
            try:
                return {
                    ">": first > second,
                    ">=": first >= second,
                    "<": first < second,
                    "<=": first <= second,
                }[node["value"]]
            except TypeError:
                return False
        if node_type == TOK_FLATTEN:
            original = self.visit(node["children"][0], value)
            if not is_array(original):
                self.debug.append("Flatten expressions apply to arrays only. If you want an empty array, use a JSON literal: `[]`")
                return None
            merged: list[Any] = []
            for current in original:
                if is_array(current):
                    merged.extend(current)
                else:
                    merged.append(current)
            return merged
        if node_type == "Identity":
            return value
        if node_type == "ArrayExpression":
            return [self.visit(child, value) for child in node["children"]]
        if node_type == "ObjectExpression":
            collected: dict[str, Any] = {}
            for child in node["children"]:
                if child["name"] in collected:
                    self.debug.append(f"Duplicate key: '{child['name']}'")
                collected[child["name"]] = self.visit(child["value"], value)
            return collected
        if node_type == "OrExpression":
            first = self.visit(node["children"][0], value)
            return first if to_boolean(first) else self.visit(node["children"][1], value)
        if node_type == "AndExpression":
            first = self.visit(node["children"][0], value)
            return first if not to_boolean(first) else self.visit(node["children"][1], value)
        if node_type == "AddExpression":
            first, second = _balance_array_operands(self.visit(node["children"][0], value), self.visit(node["children"][1], value))
            return self.apply_operator(first, second, "+")
        if node_type == "ConcatenateExpression":
            first, second = _balance_array_operands(self.visit(node["children"][0], value), self.visit(node["children"][1], value))
            if is_array_type(first):
                first = match_type([TYPE_ARRAY_STRING], first, "concatenate", self.to_number, self.to_string)
            else:
                first = match_type([TYPE_STRING], first, "concatenate", self.to_number, self.to_string)
            if is_array_type(second):
                second = match_type([TYPE_ARRAY_STRING], second, "concatenate", self.to_number, self.to_string)
            else:
                second = match_type([TYPE_STRING], second, "concatenate", self.to_number, self.to_string)
            return self.apply_operator(first, second, "&")
        if node_type == "UnionExpression":
            first = self.visit(node["children"][0], value)
            second = self.visit(node["children"][1], value)
            first = [None] if first is None else match_type([TYPE_ARRAY], first, "union", self.to_number, self.to_string)
            second = [None] if second is None else match_type([TYPE_ARRAY], second, "union", self.to_number, self.to_string)
            return first + second
        if node_type == "SubtractExpression":
            first, second = _balance_array_operands(self.visit(node["children"][0], value), self.visit(node["children"][1], value))
            return self.apply_operator(first, second, "-")
        if node_type == "MultiplyExpression":
            first, second = _balance_array_operands(self.visit(node["children"][0], value), self.visit(node["children"][1], value))
            return self.apply_operator(first, second, "*")
        if node_type == "DivideExpression":
            first, second = _balance_array_operands(self.visit(node["children"][0], value), self.visit(node["children"][1], value))
            return self.apply_operator(first, second, "/")
        if node_type == "NotExpression":
            return not to_boolean(self.visit(node["children"][0], value))
        if node_type == "UnaryMinusExpression":
            first = self.visit(node["children"][0], value)
            try:
                return self.to_number(first) * -1
            except Exception as exc:
                raise type_error(f'Failed to convert "{first}" to number') from exc
        if node_type in {"String", "Literal", "Number", "Integer"}:
            return node["value"]
        if node_type == TOK_PIPE:
            return self.visit(node["children"][1], self.visit(node["children"][0], value))
        if node_type == TOK_CURRENT:
            return value
        if node_type == TOK_GLOBAL:
            return self.globals.get(node["name"])
        if node_type == "Function":
            if node["name"] == "if":
                return self.runtime.call_function(node["name"], node["children"], value, self, False)
            resolved_args = [self.visit(child, value) for child in node["children"]]
            return self.runtime.call_function(node["name"], resolved_args, value, self)
        if node_type == "ExpressionReference":
            ref_node = node["children"][0]
            ref_node["jmespathType"] = TOK_EXPREF
            return ref_node
        raise evaluation_error(f"Unsupported AST node type: {node_type}")

    def compute_slice_params(self, array_length: int, slice_params: list[int | None]) -> tuple[int, int, int]:
        start, stop, step = slice_params
        if step is None:
            step = 1
        elif step == 0:
            raise evaluation_error("Invalid slice, step cannot be 0")
        negative = step < 0
        if start is None:
            start = array_length - 1 if negative else 0
        else:
            start = self._cap_slice_range(array_length, start, step)
        if stop is None:
            stop = -1 if negative else array_length
        else:
            stop = self._cap_slice_range(array_length, stop, step)
        return start, stop, step

    @staticmethod
    def _cap_slice_range(array_length: int, actual: int, step: int) -> int:
        if actual < 0:
            actual += array_length
            if actual < 0:
                return -1 if step < 0 else 0
        elif actual >= array_length:
            return array_length - 1 if step < 0 else array_length
        return actual

    def apply_operator(self, first: Any, second: Any, operator: str) -> Any:
        if is_array(first) and is_array(second):
            return [self.apply_operator(a, b, operator) for a, b in zip(first, second)]
        if is_array(first):
            return [self.apply_operator(item, second, operator) for item in first]
        if is_array(second):
            return [self.apply_operator(first, item, operator) for item in second]
        if operator == "&":
            return self.to_string(first) + self.to_string(second)
        if operator == "*":
            return self.to_number(first) * self.to_number(second)
        left = self.to_number(first)
        right = self.to_number(second)
        if operator == "+":
            return left + right
        if operator == "-":
            return left - right
        try:
            result = left / right
        except ZeroDivisionError as exc:
            raise evaluation_error(f"Division by zero {first}/{second}") from exc
        if not math.isfinite(result):
            raise evaluation_error(f"Division by zero {first}/{second}")
        return result
