# Copyright 2026 Adobe. All rights reserved.
# This file is licensed to you under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License. You may obtain a copy
# of the License at http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software distributed under
# the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR REPRESENTATIONS
# OF ANY KIND, either express or implied. See the License for the specific language
# governing permissions and limitations under the License.

"""Type discovery and coercion helpers."""

from __future__ import annotations

from typing import Any

from ._errors import type_error
from .data_types import (
    TYPE_ANY,
    TYPE_ARRAY,
    TYPE_ARRAY_ARRAY,
    TYPE_ARRAY_NUMBER,
    TYPE_ARRAY_STRING,
    TYPE_BOOLEAN,
    TYPE_EMPTY_ARRAY,
    TYPE_EXPREF,
    TYPE_NAME_TABLE,
    TYPE_NULL,
    TYPE_NUMBER,
    TYPE_OBJECT,
    TYPE_STRING,
)
from .tokens import TOK_EXPREF
from .utils import get_value_of, json_clone


ARRAY_TYPE_IDS = {
    TYPE_ARRAY,
    TYPE_ARRAY_NUMBER,
    TYPE_ARRAY_STRING,
    TYPE_ARRAY_ARRAY,
    TYPE_EMPTY_ARRAY,
}


def is_array_type(value: Any) -> bool:
    return get_type(value) in ARRAY_TYPE_IDS


def _flatten(values: list[Any]) -> list[Any]:
    result: list[Any] = []
    for value in values:
        if isinstance(value, list):
            result.extend(_flatten(value))
        else:
            result.append(value)
    return result


def get_type(input_obj: Any) -> int:
    if input_obj is None:
        return TYPE_NULL
    if isinstance(input_obj, bool):
        return TYPE_BOOLEAN
    if isinstance(input_obj, (int, float)) and not isinstance(input_obj, bool):
        return TYPE_NUMBER
    if isinstance(input_obj, str):
        return TYPE_STRING
    if isinstance(input_obj, list):
        if not input_obj:
            return TYPE_EMPTY_ARRAY
        flattened = _flatten(input_obj)
        if all(get_type(item) == TYPE_NUMBER for item in flattened):
            return TYPE_ARRAY_NUMBER
        if all(get_type(item) == TYPE_STRING for item in flattened):
            return TYPE_ARRAY_STRING
        if all(is_array_type(item) for item in input_obj):
            return TYPE_ARRAY_ARRAY
        return TYPE_ARRAY
    if isinstance(input_obj, dict) and input_obj.get("jmespathType") == TOK_EXPREF:
        return TYPE_EXPREF
    if isinstance(input_obj, dict):
        return TYPE_OBJECT
    cloned = json_clone(input_obj)
    return get_type(cloned)


def get_type_name(value: Any) -> str:
    return TYPE_NAME_TABLE[get_type(value)]


def _supported_conversion(source: int, target: int) -> bool:
    pairs = {
        TYPE_NUMBER: {TYPE_STRING, TYPE_ARRAY, TYPE_ARRAY_NUMBER, TYPE_BOOLEAN},
        TYPE_BOOLEAN: {TYPE_STRING, TYPE_NUMBER, TYPE_ARRAY},
        TYPE_ARRAY: {TYPE_BOOLEAN, TYPE_ARRAY_STRING, TYPE_ARRAY_NUMBER},
        TYPE_ARRAY_NUMBER: {TYPE_BOOLEAN, TYPE_ARRAY_STRING, TYPE_ARRAY},
        TYPE_ARRAY_STRING: {TYPE_BOOLEAN, TYPE_ARRAY_NUMBER, TYPE_ARRAY},
        TYPE_ARRAY_ARRAY: {TYPE_BOOLEAN},
        TYPE_EMPTY_ARRAY: {TYPE_BOOLEAN},
        TYPE_OBJECT: {TYPE_BOOLEAN},
        TYPE_NULL: {TYPE_STRING, TYPE_NUMBER, TYPE_BOOLEAN},
        TYPE_STRING: {TYPE_NUMBER, TYPE_ARRAY_STRING, TYPE_ARRAY, TYPE_BOOLEAN},
    }
    return target in pairs.get(source, set())


def match_type(expected_list: list[int], arg_value: Any, context: str, to_number, to_string):
    actual = get_type(arg_value)
    if isinstance(arg_value, dict) and arg_value.get("jmespathType") == TOK_EXPREF and TYPE_EXPREF not in expected_list:
        raise type_error(f"{context} does not accept an expression reference argument.")

    def matches(expected: int, found: int) -> bool:
        return (
            expected == found
            or expected == TYPE_ANY
            or (expected == TYPE_ARRAY and found in ARRAY_TYPE_IDS)
            or (expected in ARRAY_TYPE_IDS and found == TYPE_EMPTY_ARRAY)
        )

    if any(matches(expected, actual) for expected in expected_list):
        if TYPE_ANY not in expected_list and actual in {
            TYPE_NUMBER,
            TYPE_STRING,
            TYPE_BOOLEAN,
            TYPE_NULL,
        }:
            return get_value_of(arg_value)
        if TYPE_ANY not in expected_list and TYPE_ARRAY not in expected_list and actual in {
            TYPE_ARRAY_NUMBER,
            TYPE_ARRAY_STRING,
            TYPE_ARRAY_ARRAY,
            TYPE_EMPTY_ARRAY,
        }:
            return get_value_of(arg_value)
        return arg_value

    filtered = [expected for expected in expected_list if _supported_conversion(actual, expected)]
    if not filtered:
        raise type_error(
            f"{context} expected argument to be type {TYPE_NAME_TABLE[expected_list[0]]} "
            f"but received type {TYPE_NAME_TABLE[actual]} instead."
        )
    exact_match = len(filtered) > 1
    expected = filtered[0]

    if exact_match:
        names = ", ".join(TYPE_NAME_TABLE[item] for item in expected_list)
        raise type_error(f"{context} cannot process type: {TYPE_NAME_TABLE[actual]}. Must be one of: {names}.")

    if actual in ARRAY_TYPE_IDS:
        if expected == TYPE_BOOLEAN:
            return len(arg_value) > 0
        if expected == TYPE_ARRAY_STRING:
            return [to_string(item) if not isinstance(item, list) else [to_string(v) for v in item] for item in arg_value]
        if expected == TYPE_ARRAY_NUMBER:
            return [to_number(item) if not isinstance(item, list) else [to_number(v) for v in item] for item in arg_value]
        if expected == TYPE_ARRAY_ARRAY:
            return [item if isinstance(item, list) else [item] for item in arg_value]

    if actual == TYPE_OBJECT and expected == TYPE_BOOLEAN:
        return len(arg_value) > 0

    if not is_array_type(actual) and actual != TYPE_OBJECT:
        if expected == TYPE_ARRAY_STRING:
            return [to_string(arg_value)]
        if expected == TYPE_ARRAY_NUMBER:
            return [to_number(arg_value)]
        if expected == TYPE_ARRAY:
            return [arg_value]
        if expected == TYPE_NUMBER:
            return to_number(arg_value)
        if expected == TYPE_STRING:
            return to_string(arg_value)
        if expected == TYPE_BOOLEAN:
            return bool(arg_value)

    raise type_error(
        f"{context} expected argument to be type {TYPE_NAME_TABLE[expected]} "
        f"but received type {TYPE_NAME_TABLE[actual]} instead."
    )
