# Copyright 2026 Adobe. All rights reserved.
# This file is licensed to you under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License. You may obtain a copy
# of the License at http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software distributed under
# the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR REPRESENTATIONS
# OF ANY KIND, either express or implied. See the License for the specific language
# governing permissions and limitations under the License.

"""Utility helpers for JSON Formula runtime behavior."""

from __future__ import annotations

import json
from typing import Any

from .object_model import Field


def is_array(value: Any) -> bool:
    return isinstance(value, list)


def is_object(value: Any) -> bool:
    return isinstance(value, dict)


def get_value_of(value: Any) -> Any:
    if value is None:
        return value
    if isinstance(value, list):
        return [get_value_of(item) for item in value]
    if isinstance(value, dict):
        return {key: get_value_of(item) for key, item in value.items()}
    if isinstance(value, Field):
        return value.value_of
    if hasattr(value, "value_of"):
        return value.value_of
    return value


def to_boolean(value: Any) -> bool:
    if value is None:
        return False
    candidate = get_value_of(value)
    if isinstance(candidate, list):
        return len(candidate) > 0
    if isinstance(candidate, dict):
        return len(candidate) > 0
    return bool(candidate)


def strict_deep_equal(lhs: Any, rhs: Any) -> bool:
    left = get_value_of(lhs)
    right = get_value_of(rhs)
    if left == right and type(left) is type(right):
        return True
    if type(left) is not type(right):
        return False
    if isinstance(left, list):
        return len(left) == len(right) and all(strict_deep_equal(a, b) for a, b in zip(left, right))
    if isinstance(left, dict):
        return len(left) == len(right) and all(
            key in right and strict_deep_equal(value, right[key]) for key, value in left.items()
        )
    return False


def _descriptor_name(key: str) -> str:
    if key.startswith("$"):
        return "dollar_" + key[1:]
    return key


def get_property(obj: Any, key: Any) -> Any:
    if isinstance(obj, list):
        if isinstance(key, int) and 0 <= key < len(obj):
            return obj[key]
        if isinstance(key, str) and key.isdigit():
            index = int(key)
            if 0 <= index < len(obj):
                return obj[index]
        attr = _descriptor_name(str(key))
        return getattr(obj, attr, None)
    if isinstance(obj, dict):
        return obj.get(key)
    attr = _descriptor_name(str(key))
    return getattr(obj, attr, None)


def debug_available(debug: list[str], obj: Any, key: str, chain_start: str | None = None) -> None:
    try:
        if isinstance(obj, list) and obj:
            debug.append(f"Failed to find: '{key}' on an array object.")
            debug.append(f"Did you mean to use a projection? e.g. {chain_start or 'array'}[*].{key}")
            return
        debug.append(f"Failed to find: '{key}'")
        available: list[str] = []
        if isinstance(obj, dict):
            available.extend(
                f"'{name}'"
                for name in obj.keys()
                if not str(name).isdigit() and (not str(name).startswith("$") or str(key).startswith("$"))
            )
        elif obj is not None:
            for name in dir(obj):
                if name.startswith("_"):
                    continue
                if name.startswith("dollar_"):
                    rendered = "$" + name.removeprefix("dollar_")
                else:
                    rendered = name
                if rendered.startswith("$") and not str(key).startswith("$"):
                    continue
                available.append(f"'{rendered}'")
        if available:
            debug.append(f"Available fields: {available}")
    except Exception:
        return


def json_clone(value: Any) -> Any:
    def default(obj: Any) -> Any:
        if isinstance(obj, Field):
            return obj.to_json
        if hasattr(obj, "to_json"):
            return obj.to_json
        raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")

    return json.loads(json.dumps(value, default=default))
