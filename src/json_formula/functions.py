# Copyright 2026 Adobe. All rights reserved.
# This file is licensed to you under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License. You may obtain a copy
# of the License at http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software distributed under
# the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR REPRESENTATIONS
# OF ANY KIND, either express or implied. See the License for the specific language
# governing permissions and limitations under the License.

"""Built-in JSON Formula functions."""

from __future__ import annotations

import math
import random
import re
import statistics
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

from ._errors import evaluation_error, function_error, type_error
from .data_types import *
from .match_type import get_type
from .utils import get_property, get_value_of, strict_deep_equal, to_boolean


EPOCH = datetime(1970, 1, 1)


def _get_date_obj(value: float) -> datetime:
    return EPOCH + timedelta(milliseconds=round(value * 86400000))


def _get_date_num(value: datetime) -> float:
    if value.tzinfo is not None:
        epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
        return (value.astimezone(timezone.utc) - epoch).total_seconds() / 86400
    return (value - EPOCH).total_seconds() / 86400


def _valid_number(value: float, context: str) -> float:
    if math.isnan(value) or math.isinf(value):
        raise evaluation_error(f'Call to "{context}()" resulted in an invalid number')
    return value


def _to_integer(value: Any, to_number) -> int:
    candidate = get_value_of(value)
    if candidate is None:
        return 0
    if isinstance(candidate, str):
        candidate = to_number(candidate)
    return math.trunc(candidate)


def _to_json(value: Any, indent: Any, to_integer) -> str:
    import json

    candidate = get_value_of(value)
    if isinstance(candidate, str):
        return candidate
    offset = to_integer(indent) if indent is not None else 0
    kwargs = {"ensure_ascii": False}
    if offset:
        kwargs["indent"] = offset
    else:
        kwargs["separators"] = (",", ":")
    return json.dumps(candidate, **kwargs)


def _balance_arrays(args: list[Any]) -> list[list[Any]]:
    max_len = max(len(item) if isinstance(item, list) else 0 for item in args)
    if max_len == 0:
        return []
    prepared = []
    for arg in args:
        if isinstance(arg, list):
            prepared.append(arg + [None] * (max_len - len(arg)))
        else:
            prepared.append([arg] * max_len)
    return [[prepared[column][row] for column in range(len(prepared))] for row in range(max_len)]


def _evaluate(args: list[Any], fn):
    if any(isinstance(arg, list) for arg in args):
        return [_evaluate(row, fn) for row in _balance_arrays(args)]
    return fn(*args)


def _normalize_expref(node: Any) -> Any:
    if isinstance(node, dict):
        return tuple(sorted((key, _normalize_expref(value)) for key, value in node.items() if key != "jmespathType"))
    if isinstance(node, list):
        return tuple(_normalize_expref(item) for item in node)
    return node


def _flatten(values: Iterable[Any]) -> list[Any]:
    flattened: list[Any] = []
    for value in values:
        if isinstance(value, list):
            flattened.extend(_flatten(value))
        else:
            flattened.append(value)
    return flattened


def _numeric_values(values: Any, to_number, *, coerce: bool) -> list[float]:
    source = values if isinstance(values, list) else [values]
    flattened = _flatten(source)
    if not flattened:
        raise evaluation_error("Function requires at least one value")
    result: list[float] = []
    for item in flattened:
        if coerce:
            result.append(float(to_number(item)))
        else:
            if not isinstance(item, (int, float)) or isinstance(item, bool):
                raise evaluation_error("Function encountered a non-numeric value")
            result.append(float(item))
    return result


def _avg(values: Any) -> float:
    nums = [float(get_value_of(item)) for item in _flatten(values if isinstance(values, list) else [values]) if get_type(item) == TYPE_NUMBER]
    if not nums:
        raise evaluation_error("avg() requires at least one argument")
    return sum(nums) / len(nums)


def _sum(values: Any) -> float:
    total = 0.0
    for item in _flatten(values if isinstance(values, list) else [values]):
        if get_type(item) == TYPE_NUMBER:
            total += float(get_value_of(item))
    return total


def _avgA(values: Any, to_number) -> float:
    filtered = [item for item in _flatten(values if isinstance(values, list) else [values]) if get_type(item) != TYPE_NULL]
    try:
        numbers = [to_number(item) for item in filtered]
    except Exception as exc:
        raise type_error("avgA() received non-numeric parameters") from exc
    if not numbers:
        raise evaluation_error("avg() requires at least one argument")
    return sum(numbers) / len(numbers)


def _datedif(date1_arg: float, date2_arg: float, unit_arg: str) -> int:
    unit = str(unit_arg).lower()
    date1 = _get_date_obj(date1_arg)
    date2 = _get_date_obj(date2_arg)
    if date2 == date1:
        return 0
    if date2 < date1:
        raise function_error("end_date must be >= start_date in datedif()")
    if unit == "d":
        return math.floor(_get_date_num(date2) - _get_date_num(date1))
    year_diff = date2.year - date1.year
    month_diff = date2.month - date1.month
    day_diff = date2.day - date1.day
    if unit == "y":
        years = year_diff
        if month_diff < 0 or (month_diff == 0 and day_diff < 0):
            years -= 1
        return years
    if unit == "m":
        return year_diff * 12 + month_diff + (-1 if day_diff < 0 else 0)
    if unit == "ym":
        if day_diff < 0:
            month_diff -= 1
        if month_diff <= 0 and year_diff > 0:
            return 12 + month_diff
        return month_diff
    if unit == "yd":
        if day_diff < 0:
            month_diff -= 1
        date2 = date2.replace(year=date1.year + 1 if month_diff < 0 else date1.year)
        return math.floor(_get_date_num(date2) - _get_date_num(date1))
    raise function_error(f'Unrecognized unit parameter "{unit}" for datedif()')


def _ends_with(search_arg: str, suffix_arg: str) -> bool:
    search = _scalar_text(search_arg)
    suffix = _scalar_text(suffix_arg)
    return list(search)[-len(list(suffix)) :] == list(suffix)


def _contains_text(subject: Any, search: Any, to_string) -> bool:
    if get_type(get_value_of(search)) != TYPE_STRING:
        raise type_error("contains() requires a string search value for string subjects")
    return to_string(search) in to_string(subject)


def _eomonth(date_arg: float, months_arg: Any, to_integer) -> float:
    js_date = _get_date_obj(date_arg)
    months = to_integer(months_arg)
    year = js_date.year + ((js_date.month - 1 + months + 1) // 12)
    month = ((js_date.month - 1 + months + 1) % 12) + 1
    first_of_next = datetime(year, month, 1)
    last_day = first_of_next - timedelta(days=1)
    return _get_date_num(last_day)


def _find(query_arg: str, text_arg: str, offset_arg: Any, to_integer) -> int | None:
    query = list(_scalar_text(query_arg))
    text = list(_scalar_text(text_arg))
    offset = to_integer(offset_arg)
    if offset < 0:
        raise evaluation_error("find() start position must be >= 0")
    if not query:
        return None if offset > len(text) else offset
    for index in range(offset, len(text)):
        if text[index : index + len(query)] == query:
            return index
    return None


def _proper(value: Any) -> str:
    import re

    def capitalize(word: str) -> str:
        return word[:1].upper() + word[1:].lower()

    original = _scalar_text(value)
    parts = re.findall(r"[\s\d\W_]+|[^\s\d\W_]+", original, re.UNICODE)
    return "".join(capitalize(part) for part in parts) if parts else capitalize(original)


def _rept(text_arg: Any, count_arg: Any, to_integer) -> str:
    text = _scalar_text(text_arg)
    count = to_integer(count_arg)
    if count < 0:
        raise evaluation_error("rept() count must be greater than or equal to 0")
    return text * count


def _search(find_text: Any, within_text: Any, start_pos: Any, to_integer) -> list[Any]:
    find_text = _scalar_text(find_text)
    within_text = _scalar_text(within_text)
    start = to_integer(start_pos)
    if start < 0:
        raise function_error("search() startPos must be greater than or equal to 0")
    if within_text == "":
        return []
    glob: list[str] = []
    escape = False
    for char in find_text:
        if escape:
            glob.append(char)
            escape = False
        elif char == "\\":
            escape = True
        elif char == "?":
            glob.append("dot")
        elif char == "*":
            if not glob or glob[-1] != "star":
                glob.append("star")
        else:
            glob.append(char)

    def test_match(array: list[str], pattern: list[str], matched: list[str]) -> list[str] | None:
        if not pattern:
            return matched
        if not array:
            return None
        token = pattern[0]
        remainder = pattern[1:]
        is_star = token == "star"
        if is_star:
            if len(pattern) == 1:
                return matched
            token = pattern[1]
            remainder = pattern[2:]
        if array[0] == token or token == "dot":
            return test_match(array[1:], remainder, matched + [array[0]])
        if is_star:
            return test_match(array[1:], pattern, matched + [array[0]])
        return None

    chars = list(within_text)
    for index in range(start, len(chars)):
        result = test_match(chars[index:], glob, [])
        if result is not None:
            return [index, "".join(result)]
    return []


def _mod(a: float, b: float) -> float:
    try:
        result = a % b
    except ZeroDivisionError as exc:
        raise evaluation_error(f"Bad parameter for mod: '{a} % {b}'") from exc
    if math.isnan(result):
        raise evaluation_error(f"Bad parameter for mod: '{a} % {b}'")
    return result


def _split(value: Any, separator: Any) -> list[str]:
    source = _scalar_text(value)
    needle = _scalar_text(separator)
    return list(source) if needle == "" else source.split(needle)


def _has_property(container: Any, key: Any) -> bool:
    key = get_value_of(key)
    if container is not None and isinstance(key, str) and key.startswith("$"):
        descriptor = "dollar_" + key[1:]
        if getattr(container, descriptor, None) is not None or get_property(container, key) is not None:
            return True
    if container is not None and isinstance(key, str) and key.startswith("$") and get_property(get_value_of(container), key) is not None:
        return True
    if container is not None and get_property(container, key) is not None and not isinstance(get_value_of(container), (dict, list)):
        return True
    obj = get_value_of(container)
    if obj is None:
        return False
    if isinstance(obj, dict):
        if not isinstance(key, str):
            raise type_error("hasProperty(): Object key must be a string")
        return key in obj
    if isinstance(obj, list):
        if isinstance(key, (int, float)) and not isinstance(key, bool):
            return 0 <= math.trunc(key) < len(obj)
        if isinstance(key, str) and key.isdigit():
            index = int(key)
            return 0 <= index < len(obj)
        raise type_error("hasProperty(): Array index must be an integer")
    raise type_error("First parameter to hasProperty() must be either an object or array.")


def _math_unary(name: str, fn):
    def inner(value):
        try:
            return _valid_number(fn(value), name)
        except ValueError as exc:
            raise evaluation_error(f'Call to "{name}()" resulted in an invalid number') from exc

    return inner


def _entries(subject: Any) -> list[list[Any]]:
    obj = get_value_of(subject)
    if isinstance(obj, list):
        return [[str(index), value] for index, value in enumerate(obj)]
    return [[key, value] for key, value in obj.items()]


def _from_entries(array: list[Any]) -> dict[str, Any]:
    if not all(isinstance(item, list) and len(item) == 2 and isinstance(get_value_of(item[0]), str) for item in array):
        raise type_error("fromEntries() requires an array of key value pairs")
    return {get_value_of(key): value for key, value in array}


def _join(array: list[Any], glue: Any, to_integer) -> str:
    return str(glue).join(_to_json(item, 0, to_integer) for item in array)


def _value(subject: Any, index: Any, debug: list[str]) -> Any:
    index = get_value_of(index)
    index_type = get_type(index)
    container = get_value_of(subject)
    if subject is not None and isinstance(index, str) and index.startswith("$") and get_property(subject, index) is not None:
        return get_property(subject, index)
    if subject is not None and get_property(subject, index) is not None and not isinstance(container, (dict, list)):
        return get_property(subject, index)
    if container is None:
        return None
    subject_array = isinstance(container, list)
    if not (isinstance(container, dict) or subject_array):
        raise type_error("First parameter to value() must be one of: object, array, null.")
    lookup = index
    if subject_array:
        if index_type != TYPE_NUMBER:
            raise type_error("value() requires an integer index for arrays")
        lookup = math.trunc(index)
    elif index_type != TYPE_STRING:
        raise type_error("value() requires a string index for objects")
    result = get_property(subject if subject_array or isinstance(subject, dict) else container, lookup)
    if result is None:
        if subject_array:
            debug.append(f"Index: {lookup} out of range for array size: {len(container)}")
        return None
    return result


def _substitute(source: Any, old_string: Any, replacement_string: Any, nearest: int) -> str:
    src = list(_scalar_text(source))
    old = list(_scalar_text(old_string))
    replacement = list(_scalar_text(replacement_string))
    if not old:
        return _scalar_text(source)
    replace_all = nearest < 0
    which = nearest + 1
    found = 0
    result: list[str] = []
    index = 0
    while index < len(src):
        match = old == src[index : index + len(old)]
        if match:
            found += 1
        if match and (replace_all or found == which):
            result.extend(replacement)
            index += len(old)
        else:
            result.append(src[index])
            index += 1
    return "".join(result)


def _locale_upper(text: str, language: str) -> str:
    if language.lower().startswith(("tr", "az")):
        mapped = []
        for char in text:
            if char == "i":
                mapped.append("İ")
            elif char == "ı":
                mapped.append("I")
            else:
                mapped.append(char.upper())
        return "".join(mapped)
    return text.upper()


def _locale_lower(text: str, language: str) -> str:
    if language.lower().startswith(("tr", "az")):
        mapped = []
        for char in text:
            if char == "I":
                mapped.append("ı")
            elif char == "İ":
                mapped.append("i")
            else:
                mapped.append(char.lower())
        return "".join(mapped)
    return text.lower()


def _casefold_value(value: Any, language: str) -> str:
    text = _scalar_text(value)
    return _locale_lower(_locale_upper(text, language), language)


def _trunc(number: float, digits_arg: Any, to_integer) -> float:
    digits = to_integer(digits_arg)
    method = math.floor if number >= 0 else math.ceil
    return method(number * (10 ** digits)) / (10 ** digits)


def _weekday(date_arg: float, type_arg: Any, to_integer) -> int:
    js_date = _get_date_obj(date_arg)
    # Python Monday=0; JS Sunday=0
    day = (js_date.weekday() + 1) % 7
    return_type = to_integer(type_arg)
    if return_type == 1:
        return day + 1
    if return_type == 2:
        return ((day + 6) % 7) + 1
    if return_type == 3:
        return (day + 6) % 7
    raise function_error(f'Unsupported returnType: "{type_arg}" for weekday()')


def _replace(subject: Any, start_arg: Any, length_arg: Any, replacement: Any) -> Any:
    start_pos = math.trunc(start_arg)
    num_elements = math.trunc(length_arg)
    if start_pos < 0:
        raise evaluation_error("replace() start position must be greater than or equal to 0")
    if num_elements < 0:
        raise evaluation_error("replace() length must be greater than or equal to 0")
    source = get_value_of(subject)
    if isinstance(source, list):
        replacement_value = get_value_of(replacement)
        if not isinstance(replacement_value, list):
            replacement_value = [replacement_value]
        copy = list(source)
        copy[start_pos : start_pos + num_elements] = replacement_value
        return copy
    replacement_value = get_value_of(replacement)
    if isinstance(replacement_value, (list, dict)):
        raise type_error("replace() replacement must not be an array or object")
    chars = list("" if source is None else str(source))
    chars[start_pos : start_pos + num_elements] = ["" if replacement_value is None else str(replacement_value)]
    return "".join(chars)


def _time(args: list[Any], to_integer) -> float:
    hours = to_integer(args[0])
    minutes = to_integer(args[1]) if len(args) > 1 else 0
    seconds = to_integer(args[2]) if len(args) > 2 else 0
    return _get_date_num(datetime(1970, 1, 1) + timedelta(hours=hours, minutes=minutes, seconds=seconds))


def _datetime_value(args: list[Any], to_integer) -> float:
    year = to_integer(args[0])
    month = to_integer(args[1])
    day = to_integer(args[2])
    hour = to_integer(args[3]) if len(args) > 3 else 0
    minute = to_integer(args[4]) if len(args) > 4 else 0
    second = to_integer(args[5]) if len(args) > 5 else 0
    millisecond = to_integer(args[6]) if len(args) > 6 else 0
    year += (month - 1) // 12
    month = ((month - 1) % 12) + 1
    base = datetime(year, month, 1)
    value = base + timedelta(days=day - 1, hours=hour, minutes=minute, seconds=second, milliseconds=millisecond)
    return _get_date_num(value)


def _to_number(args: list[Any], to_number, to_integer, debug: list[str]) -> Any:
    def convert(value, base):
        num = get_value_of(value)
        if isinstance(num, str) and base != 10:
            digit_checks = {
                2: "01",
                8: "01234567",
                16: "0123456789abcdefABCDEF",
            }
            if base not in digit_checks:
                raise evaluation_error(f'Invalid base: "{base}" for toNumber()')
            if num == "":
                return 0
            sign = 1
            stripped = num.strip()
            if stripped.startswith("-"):
                sign = -1
                stripped = stripped[1:]
            elif stripped.startswith("+"):
                stripped = stripped[1:]
            parts = stripped.split(".")
            if len(parts) > 2 or any(any(ch not in digit_checks[base] for ch in part) for part in parts if part):
                debug.append(f'Failed to convert "{num}" base "{base}" to number')
                return None
            integer = int(parts[0] or "0", base)
            decimal = 0.0
            if len(parts) == 2 and parts[1]:
                decimal = int(parts[1], base) * (base ** (-len(parts[1])))
            return sign * (integer + decimal)
        try:
            if num == "":
                return 0
            return to_number(num)
        except Exception:
            debug.append(f'Failed to convert "{str(num)[:20] if num is not None else num}" to number')
            return None

    base = 10
    if len(args) > 1:
        base = [to_integer(item) for item in args[1]] if isinstance(args[1], list) else to_integer(args[1])
    return _evaluate([args[0], base], convert)


def _stdev(values: list[float], population: bool) -> float:
    if len(values) < 2 and not population:
        raise evaluation_error("At least two values are required")
    return statistics.pstdev(values) if population else statistics.stdev(values)


def _stdev_plain(values: Any, population: bool) -> float:
    nums = [get_value_of(item) for item in _flatten(values if isinstance(values, list) else [values]) if get_type(item) == TYPE_NUMBER]
    if population:
        if len(nums) == 0:
            raise evaluation_error("stdevp() must have at least one value")
    elif len(nums) <= 1:
        raise evaluation_error("stdev() must have at least two values")
    return _stdev([float(v) for v in nums], population)


def _stdev_coerced(values: Any, population: bool, to_number) -> float:
    filtered = [item for item in _flatten(values if isinstance(values, list) else [values]) if get_type(item) != TYPE_NULL]
    try:
        nums = [to_number(item) for item in filtered]
    except Exception as exc:
        name = "stdevpA()" if population else "stdevA()"
        raise evaluation_error(f"{name} received non-numeric parameters") from exc
    if population:
        if len(nums) == 0:
            raise evaluation_error("stdevp() must have at least one value")
    elif len(nums) <= 1:
        raise evaluation_error("stdevA() must have at least two values")
    return _stdev([float(v) for v in nums], population)


def _deep_scan(value: Any, key: Any) -> list[Any]:
    results: list[Any] = []
    if isinstance(key, (int, float)) and not isinstance(key, bool):
        name = math.trunc(key)
        check_arrays = True
    else:
        name = _scalar_text(key)
        check_arrays = False
    def scan(node):
        if node is None:
            return
        node = get_value_of(node)
        if isinstance(node, list):
            if check_arrays and 0 <= name < len(node):
                results.append(node[name])
            for child in node:
                scan(child)
        elif isinstance(node, dict):
            for child_key, child_value in node.items():
                if not check_arrays and child_key == name:
                    results.append(child_value)
                scan(child_value)
    scan(value)
    return results


def _sort_by(values: list[Any], expr: dict[str, Any], runtime) -> list[Any]:
    sorted_array = list(values)
    if not sorted_array:
        return sorted_array
    required = get_type(get_value_of(runtime.interpreter.visit(expr, sorted_array[0])))
    if required not in {TYPE_NUMBER, TYPE_STRING}:
        raise type_error("Bad data type for sortBy()")
    decorated = list(enumerate(sorted_array))

    def sort_key(entry):
        index, item = entry
        value = get_value_of(runtime.interpreter.visit(expr, item))
        if get_type(value) != required:
            raise type_error("Bad data type for sortBy()")
        return (value, index)

    decorated.sort(key=sort_key)
    return [item for _, item in decorated]


def _register(runtime, name: str, expr: dict[str, Any], variadic: bool) -> dict[str, Any] | None:
    if not name or not name.replace("_", "").isalnum() or not (name[0].isalpha() or name[0] == "_"):
        raise function_error(f'Invalid function name: "{name}"')
    existing = runtime.function_table.get(name)
    if existing is not None:
        existing_expr = existing.get("_exprefNode")
        if existing_expr is None or _normalize_expref(existing_expr) != _normalize_expref(expr):
            raise function_error(f'Cannot override function: "{name}" with a different definition')

    def registered(args, _data, interpreter):
        if variadic:
            return interpreter.visit(expr, args)
        return interpreter.visit(expr, args[0] if args else None)

    runtime.function_table[name] = {
        "func": registered,
        "signature": [{"types": [TYPE_ANY], "optional": True, "variadic": variadic}],
        "_exprefNode": expr,
    }
    return {}


def _max_or_min(values: Any, *, choose_max: bool, to_number, coerce: bool) -> float:
    numbers = _numeric_values(values, to_number, coerce=coerce)
    return max(numbers) if choose_max else min(numbers)


def _max_min_variadic(args: list[Any], *, choose_max: bool, to_number, coerce: bool) -> float:
    collected: list[Any] = []
    for arg in args:
        if isinstance(arg, list):
            collected.extend(_flatten(arg))
        else:
            collected.append(arg)
    return _max_or_min(collected, choose_max=choose_max, to_number=to_number, coerce=coerce)


def _max_plain(args: list[Any]) -> float:
    values = [get_value_of(item) for item in _flatten(args) if isinstance(get_value_of(item), (int, float)) and not isinstance(get_value_of(item), bool)]
    return max(values) if values else 0


def _min_plain(args: list[Any]) -> float:
    values = [get_value_of(item) for item in _flatten(args) if isinstance(get_value_of(item), (int, float)) and not isinstance(get_value_of(item), bool)]
    return min(values) if values else 0


def _max_coerced(args: list[Any], to_number) -> float:
    values = [get_value_of(item) for item in _flatten(args) if get_value_of(item) is not None]
    if not values:
        return 0
    try:
        coerced = [to_number(item) for item in values]
    except Exception as exc:
        raise type_error("maxA() received non-numeric parameters") from exc
    return max(coerced) if coerced else 0


def _min_coerced(args: list[Any], to_number) -> float:
    values = [get_value_of(item) for item in _flatten(args) if get_value_of(item) is not None]
    if not values:
        return 0
    try:
        coerced = [to_number(item) for item in values]
    except Exception as exc:
        raise type_error("minA() received non-numeric parameters") from exc
    return min(coerced) if coerced else 0


def build_functions(runtime, is_object, to_number, get_type, is_array_type, value_of, to_string, debug):
    to_integer = lambda value: _to_integer(value, to_number)

    return {
        "abs": {"func": lambda args, *_: _evaluate(args, abs), "signature": [{"types": [TYPE_NUMBER, TYPE_ARRAY_NUMBER]}]},
        "acos": {"func": lambda args, *_: _evaluate(args, _math_unary("acos", math.acos)), "signature": [{"types": [TYPE_NUMBER, TYPE_ARRAY_NUMBER]}]},
        "and": {"func": lambda args, *_: all(to_boolean(value_of(arg)) for arg in args), "signature": [{"types": [TYPE_ANY], "variadic": True}]},
        "asin": {"func": lambda args, *_: _evaluate(args, _math_unary("asin", math.asin)), "signature": [{"types": [TYPE_NUMBER, TYPE_ARRAY_NUMBER]}]},
        "atan2": {"func": lambda args, *_: _evaluate(args, math.atan2), "signature": [{"types": [TYPE_NUMBER, TYPE_ARRAY_NUMBER]}, {"types": [TYPE_NUMBER, TYPE_ARRAY_NUMBER]}]},
        "avg": {"func": lambda args, *_: _avg(args[0]), "signature": [{"types": [TYPE_ARRAY]}]},
        "avgA": {"func": lambda args, *_: _avgA(args[0], to_number), "signature": [{"types": [TYPE_ARRAY]}]},
        "casefold": {
            "func": lambda args, _data, interpreter: _evaluate(args, lambda s: _casefold_value(s, interpreter.language)),
            "signature": [{"types": [TYPE_STRING, TYPE_ARRAY_STRING]}],
        },
        "ceil": {"func": lambda args, *_: _evaluate(args, math.ceil), "signature": [{"types": [TYPE_NUMBER, TYPE_ARRAY_NUMBER]}]},
        "codePoint": {"func": lambda args, *_: _evaluate(args, lambda s: ord(to_string(s)[0]) if to_string(s) else None), "signature": [{"types": [TYPE_STRING, TYPE_ARRAY_STRING]}]},
        "contains": {
            "func": lambda args, *_: any(strict_deep_equal(item, get_value_of(args[1])) for item in get_value_of(args[0]))
            if isinstance(get_value_of(args[0]), list)
            else _contains_text(args[0], args[1], to_string),
            "signature": [{"types": [TYPE_STRING, TYPE_ARRAY]}, {"types": [TYPE_ANY]}],
        },
        "cos": {"func": lambda args, *_: _evaluate(args, math.cos), "signature": [{"types": [TYPE_NUMBER, TYPE_ARRAY_NUMBER]}]},
        "datedif": {"func": lambda args, *_: _evaluate(args, _datedif), "signature": [{"types": [TYPE_NUMBER, TYPE_ARRAY_NUMBER]}, {"types": [TYPE_NUMBER, TYPE_ARRAY_NUMBER]}, {"types": [TYPE_STRING, TYPE_ARRAY_STRING]}]},
        "datetime": {
            "func": lambda args, *_: _datetime_value(args, to_integer),
            "signature": [
                {"types": [TYPE_NUMBER]},
                {"types": [TYPE_NUMBER]},
                {"types": [TYPE_NUMBER]},
                {"types": [TYPE_NUMBER], "optional": True},
                {"types": [TYPE_NUMBER], "optional": True},
                {"types": [TYPE_NUMBER], "optional": True},
                {"types": [TYPE_NUMBER], "optional": True},
            ],
        },
        "day": {"func": lambda args, *_: _evaluate(args, lambda value: _get_date_obj(value).day), "signature": [{"types": [TYPE_NUMBER, TYPE_ARRAY_NUMBER]}]},
        "debug": {
            "func": lambda args, *_: _debug_fn(args, runtime, debug, to_integer),
            "signature": [{"types": [TYPE_ANY]}, {"types": [TYPE_ANY, TYPE_EXPREF], "optional": True}],
        },
        "deepScan": {
            "func": lambda args, *_: _deep_scan(args[0], args[1]),
            "signature": [{"types": [TYPE_OBJECT, TYPE_ARRAY, TYPE_NULL]}, {"types": [TYPE_STRING, TYPE_NUMBER]}],
        },
        "endsWith": {"func": lambda args, *_: _evaluate(args, _ends_with), "signature": [{"types": [TYPE_STRING, TYPE_ARRAY_STRING]}, {"types": [TYPE_STRING, TYPE_ARRAY_STRING]}]},
        "entries": {"func": lambda args, *_: _entries(args[0]), "signature": [{"types": [TYPE_ARRAY, TYPE_OBJECT]}]},
        "eomonth": {"func": lambda args, *_: _evaluate(args, lambda d, m: _eomonth(d, m, to_integer)), "signature": [{"types": [TYPE_NUMBER, TYPE_ARRAY_NUMBER]}, {"types": [TYPE_NUMBER, TYPE_ARRAY_NUMBER]}]},
        "exp": {"func": lambda args, *_: _evaluate(args, math.exp), "signature": [{"types": [TYPE_NUMBER, TYPE_ARRAY_NUMBER]}]},
        "false": {"func": lambda _args, *_: False, "signature": []},
        "find": {"func": lambda args, *_: _evaluate(args, lambda a, b, c=0: _find(a, b, c, to_integer)), "signature": [{"types": [TYPE_STRING, TYPE_ARRAY_STRING]}, {"types": [TYPE_STRING, TYPE_ARRAY_STRING]}, {"types": [TYPE_NUMBER, TYPE_ARRAY_NUMBER], "optional": True}]},
        "floor": {"func": lambda args, *_: _evaluate(args, math.floor), "signature": [{"types": [TYPE_NUMBER, TYPE_ARRAY_NUMBER]}]},
        "fromCodePoint": {"func": lambda args, *_: _from_code_point(args[0], to_integer), "signature": [{"types": [TYPE_NUMBER, TYPE_ARRAY_NUMBER]}]},
        "fromEntries": {"func": lambda args, *_: _from_entries(args[0]), "signature": [{"types": [TYPE_ARRAY_ARRAY, TYPE_ARRAY_STRING, TYPE_ARRAY_NUMBER]}]},
        "fround": {"func": lambda args, *_: _evaluate(args, lambda value: float(value)), "signature": [{"types": [TYPE_NUMBER, TYPE_ARRAY_NUMBER]}]},
        "hasProperty": {"func": lambda args, *_: _has_property(args[0], args[1]), "signature": [{"types": [TYPE_ANY]}, {"types": [TYPE_STRING, TYPE_NUMBER]}]},
        "hour": {"func": lambda args, *_: _evaluate(args, lambda value: _get_date_obj(value).hour), "signature": [{"types": [TYPE_NUMBER, TYPE_ARRAY_NUMBER]}]},
        "if": {
            "func": lambda args, data, interpreter: _if_function(args, data, interpreter),
            "signature": [{"types": [TYPE_ANY]}, {"types": [TYPE_ANY]}, {"types": [TYPE_ANY]}],
        },
        "join": {"func": lambda args, *_: _join(args[0], args[1], to_integer), "signature": [{"types": [TYPE_ARRAY]}, {"types": [TYPE_STRING]}]},
        "keys": {"func": lambda args, *_: list(args[0].keys()), "signature": [{"types": [TYPE_OBJECT]}]},
        "left": {"func": lambda args, *_: _left(args[0], args[1] if len(args) > 1 else None, to_integer), "signature": [{"types": [TYPE_STRING, TYPE_ARRAY]}, {"types": [TYPE_NUMBER], "optional": True}]},
        "length": {"func": lambda args, *_: len(args[0]) if args[0] is not None else 0, "signature": [{"types": [TYPE_STRING, TYPE_ARRAY, TYPE_OBJECT]}]},
        "log": {"func": lambda args, *_: _evaluate(args, _math_unary("log", math.log)), "signature": [{"types": [TYPE_NUMBER, TYPE_ARRAY_NUMBER]}]},
        "log10": {"func": lambda args, *_: _evaluate(args, _math_unary("log10", math.log10)), "signature": [{"types": [TYPE_NUMBER, TYPE_ARRAY_NUMBER]}]},
        "lower": {"func": lambda args, *_: _evaluate(args, lambda s: to_string(s).lower()), "signature": [{"types": [TYPE_STRING, TYPE_ARRAY_STRING]}]},
        "map": {"func": lambda args, _data, interpreter: [interpreter.visit(args[1], item) for item in args[0]], "signature": [{"types": [TYPE_ARRAY]}, {"types": [TYPE_EXPREF]}]},
        "max": {"func": lambda args, *_: _max_plain(args), "signature": [{"types": [TYPE_ARRAY, TYPE_ANY], "variadic": True}]},
        "maxA": {"func": lambda args, *_: _max_coerced(args, to_number), "signature": [{"types": [TYPE_ARRAY, TYPE_ANY], "variadic": True}]},
        "merge": {"func": lambda args, *_: {key: value for arg in args if arg is not None for key, value in arg.items()}, "signature": [{"types": [TYPE_OBJECT, TYPE_NULL], "variadic": True}]},
        "mid": {"func": lambda args, *_: _mid(args[0], args[1], args[2], to_integer), "signature": [{"types": [TYPE_STRING, TYPE_ARRAY]}, {"types": [TYPE_NUMBER]}, {"types": [TYPE_NUMBER]}]},
        "millisecond": {"func": lambda args, *_: _evaluate(args, lambda value: _get_date_obj(value).microsecond // 1000), "signature": [{"types": [TYPE_NUMBER, TYPE_ARRAY_NUMBER]}]},
        "min": {"func": lambda args, *_: _min_plain(args), "signature": [{"types": [TYPE_ARRAY, TYPE_ANY], "variadic": True}]},
        "minA": {"func": lambda args, *_: _min_coerced(args, to_number), "signature": [{"types": [TYPE_ARRAY, TYPE_ANY], "variadic": True}]},
        "minute": {"func": lambda args, *_: _evaluate(args, lambda value: _get_date_obj(value).minute), "signature": [{"types": [TYPE_NUMBER, TYPE_ARRAY_NUMBER]}]},
        "mod": {"func": lambda args, *_: _evaluate(args, _mod), "signature": [{"types": [TYPE_NUMBER, TYPE_ARRAY_NUMBER]}, {"types": [TYPE_NUMBER, TYPE_ARRAY_NUMBER]}]},
        "month": {"func": lambda args, *_: _evaluate(args, lambda value: _get_date_obj(value).month), "signature": [{"types": [TYPE_NUMBER, TYPE_ARRAY_NUMBER]}]},
        "not": {"func": lambda args, *_: not to_boolean(value_of(args[0])), "signature": [{"types": [TYPE_ANY]}]},
        "notNull": {"func": lambda args, *_: next((arg for arg in args if get_value_of(arg) is not None), None), "signature": [{"types": [TYPE_ANY], "variadic": True}]},
        "now": {"func": lambda _args, *_: _get_date_num(datetime.now(timezone.utc)), "signature": []},
        "null": {"func": lambda _args, *_: None, "signature": []},
        "or": {"func": lambda args, *_: any(to_boolean(value_of(arg)) for arg in args), "signature": [{"types": [TYPE_ANY], "variadic": True}]},
        "power": {"func": lambda args, *_: _evaluate(args, _power), "signature": [{"types": [TYPE_NUMBER, TYPE_ARRAY_NUMBER]}, {"types": [TYPE_NUMBER, TYPE_ARRAY_NUMBER]}]},
        "proper": {"func": lambda args, *_: _evaluate(args, _proper), "signature": [{"types": [TYPE_STRING, TYPE_ARRAY_STRING]}]},
        "random": {"func": lambda _args, *_: random.random(), "signature": []},
        "reduce": {
            "func": lambda args, _data, interpreter: _reduce(args[0], args[1], interpreter, args[2] if len(args) > 2 else None),
            "signature": [{"types": [TYPE_ARRAY]}, {"types": [TYPE_EXPREF]}, {"types": [TYPE_ANY], "optional": True}],
        },
        "register": {"func": lambda args, *_: _register(runtime, args[0], args[1], False), "signature": [{"types": [TYPE_STRING]}, {"types": [TYPE_EXPREF]}]},
        "registerWithParams": {"func": lambda args, *_: _register(runtime, args[0], args[1], True), "signature": [{"types": [TYPE_STRING]}, {"types": [TYPE_EXPREF]}]},
        "replace": {"func": lambda args, *_: _replace(args[0], args[1], args[2], args[3]), "signature": [{"types": [TYPE_STRING, TYPE_ARRAY]}, {"types": [TYPE_NUMBER]}, {"types": [TYPE_NUMBER]}, {"types": [TYPE_ANY]}]},
        "rept": {"func": lambda args, *_: _evaluate(args, lambda a, b: _rept(a, b, to_integer)), "signature": [{"types": [TYPE_STRING, TYPE_ARRAY_STRING]}, {"types": [TYPE_NUMBER, TYPE_ARRAY_NUMBER]}]},
        "reverse": {"func": lambda args, *_: list(reversed(args[0])) if isinstance(args[0], list) else to_string(args[0])[::-1], "signature": [{"types": [TYPE_STRING, TYPE_ARRAY]}]},
        "right": {"func": lambda args, *_: _right(args[0], args[1] if len(args) > 1 else None, to_integer), "signature": [{"types": [TYPE_STRING, TYPE_ARRAY]}, {"types": [TYPE_NUMBER], "optional": True}]},
        "round": {"func": lambda args, *_: _evaluate([args[0], args[1] if len(args) > 1 else 0], lambda a, n: _round_half_up(a, to_integer(n))), "signature": [{"types": [TYPE_NUMBER, TYPE_ARRAY_NUMBER]}, {"types": [TYPE_NUMBER, TYPE_ARRAY_NUMBER], "optional": True}]},
        "search": {"func": lambda args, *_: _evaluate(args, lambda a, b, c=0: _search(a, b, c, to_integer)), "signature": [{"types": [TYPE_STRING, TYPE_ARRAY_STRING]}, {"types": [TYPE_STRING, TYPE_ARRAY_STRING]}, {"types": [TYPE_NUMBER, TYPE_ARRAY_NUMBER], "optional": True}]},
        "second": {"func": lambda args, *_: _evaluate(args, lambda value: _get_date_obj(value).second), "signature": [{"types": [TYPE_NUMBER, TYPE_ARRAY_NUMBER]}]},
        "sign": {"func": lambda args, *_: _evaluate(args, lambda value: 0 if value == 0 else (1 if value > 0 else -1)), "signature": [{"types": [TYPE_NUMBER, TYPE_ARRAY_NUMBER]}]},
        "sin": {"func": lambda args, *_: _evaluate(args, math.sin), "signature": [{"types": [TYPE_NUMBER, TYPE_ARRAY_NUMBER]}]},
        "sort": {"func": lambda args, *_: _sort(args[0]), "signature": [{"types": [TYPE_ARRAY]}]},
        "sortBy": {"func": lambda args, *_: _sort_by(args[0], args[1], runtime), "signature": [{"types": [TYPE_ARRAY]}, {"types": [TYPE_EXPREF]}]},
        "split": {"func": lambda args, *_: _evaluate(args, _split), "signature": [{"types": [TYPE_STRING, TYPE_ARRAY_STRING]}, {"types": [TYPE_STRING, TYPE_ARRAY_STRING]}]},
        "sqrt": {"func": lambda args, *_: _evaluate(args, _math_unary("sqrt", math.sqrt)), "signature": [{"types": [TYPE_NUMBER, TYPE_ARRAY_NUMBER]}]},
        "startsWith": {"func": lambda args, *_: _evaluate(args, lambda a, b: to_string(a).startswith(to_string(b))), "signature": [{"types": [TYPE_STRING, TYPE_ARRAY_STRING]}, {"types": [TYPE_STRING, TYPE_ARRAY_STRING]}]},
        "stdev": {"func": lambda args, *_: _stdev_plain(args[0], False), "signature": [{"types": [TYPE_ARRAY]}]},
        "stdevA": {"func": lambda args, *_: _stdev_coerced(args[0], False, to_number), "signature": [{"types": [TYPE_ARRAY]}]},
        "stdevp": {"func": lambda args, *_: _stdev_plain(args[0], True), "signature": [{"types": [TYPE_ARRAY]}]},
        "stdevpA": {"func": lambda args, *_: _stdev_coerced(args[0], True, to_number), "signature": [{"types": [TYPE_ARRAY]}]},
        "substitute": {"func": lambda args, *_: _substitute_eval(args, to_integer), "signature": [{"types": [TYPE_STRING, TYPE_ARRAY_STRING]}, {"types": [TYPE_STRING, TYPE_ARRAY_STRING]}, {"types": [TYPE_STRING, TYPE_ARRAY_STRING]}, {"types": [TYPE_NUMBER, TYPE_ARRAY_NUMBER], "optional": True}]},
        "sum": {"func": lambda args, *_: _sum(args[0]), "signature": [{"types": [TYPE_ARRAY_NUMBER, TYPE_ARRAY]}]},
        "tan": {"func": lambda args, *_: _evaluate(args, math.tan), "signature": [{"types": [TYPE_NUMBER, TYPE_ARRAY_NUMBER]}]},
        "time": {
            "func": lambda args, *_: _time(args, to_integer),
            "signature": [{"types": [TYPE_NUMBER]}, {"types": [TYPE_NUMBER], "optional": True}, {"types": [TYPE_NUMBER], "optional": True}],
        },
        "toArray": {"func": lambda args, *_: args[0] if isinstance(args[0], list) else [args[0]], "signature": [{"types": [TYPE_ANY]}]},
        "toDate": {
            "func": lambda args, *_: _to_date(args[0]),
            "signature": [{"types": [TYPE_STRING]}],
        },
        "toNumber": {"func": lambda args, *_: _to_number(args, to_number, to_integer, debug), "signature": [{"types": [TYPE_ANY]}, {"types": [TYPE_NUMBER, TYPE_ARRAY_NUMBER], "optional": True}]},
        "toString": {"func": lambda args, *_: _to_json(args[0], args[1] if len(args) > 1 else 0, to_integer), "signature": [{"types": [TYPE_ANY]}, {"types": [TYPE_NUMBER], "optional": True}]},
        "trim": {"func": lambda args, *_: _evaluate(args, _trim_spaces), "signature": [{"types": [TYPE_STRING, TYPE_ARRAY_STRING]}]},
        "true": {"func": lambda _args, *_: True, "signature": []},
        "trunc": {
            "func": lambda args, *_: _evaluate([args[0], args[1] if len(args) > 1 else 0], lambda a, n: _trunc(a, n, to_integer)),
            "signature": [{"types": [TYPE_NUMBER, TYPE_ARRAY_NUMBER]}, {"types": [TYPE_NUMBER, TYPE_ARRAY_NUMBER], "optional": True}],
        },
        "type": {"func": lambda args, *_: _type_name(args[0]), "signature": [{"types": [TYPE_ANY]}]},
        "unique": {"func": lambda args, *_: _unique(args[0]), "signature": [{"types": [TYPE_ARRAY]}]},
        "upper": {"func": lambda args, *_: _evaluate(args, lambda s: to_string(s).upper()), "signature": [{"types": [TYPE_STRING, TYPE_ARRAY_STRING]}]},
        "value": {"func": lambda args, *_: _value(args[0], args[1], debug), "signature": [{"types": [TYPE_ANY]}, {"types": [TYPE_STRING, TYPE_NUMBER]}]},
        "values": {"func": lambda args, *_: list(args[0].values()), "signature": [{"types": [TYPE_OBJECT]}]},
        "weekday": {
            "func": lambda args, *_: _evaluate([args[0], args[1] if len(args) > 1 else 1], lambda d, t: _weekday(d, t, to_integer)),
            "signature": [{"types": [TYPE_NUMBER, TYPE_ARRAY_NUMBER]}, {"types": [TYPE_NUMBER, TYPE_ARRAY_NUMBER], "optional": True}],
        },
        "year": {"func": lambda args, *_: _evaluate(args, lambda value: _get_date_obj(value).year), "signature": [{"types": [TYPE_NUMBER, TYPE_ARRAY_NUMBER]}]},
        "zip": {"func": lambda args, *_: [list(row) for row in zip(*args)], "signature": [{"types": [TYPE_ARRAY], "variadic": True}]},
    }


def _reduce(values: list[Any], expr: dict[str, Any], interpreter, initial: Any) -> Any:
    if initial is None and values:
        accumulated = values[0]
        rest = values[1:]
    else:
        accumulated = initial
        rest = values
    for index, current in enumerate(rest):
        payload = {
            "accumulated": accumulated,
            "current": current,
            "index": index,
            "array": values,
        }
        accumulated = interpreter.visit(expr, payload)
    return accumulated


def _to_date(value: str) -> float:
    iso = re.sub(r"(\d\d\d\d)(\d\d)(\d\d)", r"\1-\2-\3", value, count=1)
    iso = re.sub(r"T(\d\d)(\d\d)(\d\d)", r"T\1:\2:\3", iso, count=1)
    iso = re.sub(r"([+-]\d\d)(\d\d)$", r"\1:\2", iso)
    parts = re.split(r"[\D,zZ]+", iso)
    if len(parts) <= 3:
        if len(parts) < 3 or any(part == "" for part in parts):
            return None
    try:
        has_timezone = bool(re.search(r"(Z|z|[+-]\d\d:\d\d)$", iso))
        if len(parts) < 7 and not has_timezone:
            ranges = [99999, 12, 31, 23, 59, 59, 999]
            for idx, part in enumerate(parts):
                if part and int(part) > ranges[idx]:
                    return None
            nums = [int(part) for part in parts if part != ""]
            while len(nums) < 7:
                nums.append(0)
            parsed = datetime(nums[0], nums[1], nums[2], nums[3], nums[4], nums[5], nums[6] * 1000)
        else:
            parsed = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return _get_date_num(parsed)
    except Exception:
        return None


def _unique(values: list[Any]) -> list[Any]:
    result: list[Any] = []
    for value in values:
        if not any(strict_deep_equal(value, existing) for existing in result):
            result.append(value)
    return result


def _sort(values: list[Any]) -> list[Any]:
    numbers: list[Any] = []
    strings: list[str] = []
    booleans: list[bool] = []
    nulls: list[Any] = []
    for value in values:
        candidate = get_value_of(value)
        value_type = get_type(candidate)
        if value_type == TYPE_NUMBER:
            numbers.append(candidate)
        elif value_type == TYPE_STRING:
            strings.append(candidate)
        elif value_type == TYPE_BOOLEAN:
            booleans.append(candidate)
        elif value_type == TYPE_NULL:
            nulls.append(candidate)
        else:
            raise evaluation_error("Bad datatype for sort")
    return sorted(numbers) + sorted(strings) + booleans + nulls


def _mod(dividend: Any, divisor: Any) -> float:
    if divisor == 0:
        raise evaluation_error(f"Bad parameter for mod: '{dividend} % {divisor}'")
    result = dividend - math.trunc(dividend / divisor) * divisor
    if math.isnan(result):
        raise evaluation_error(f"Bad parameter for mod: '{dividend} % {divisor}'")
    return result


def _power(base: Any, exponent: Any) -> float:
    try:
        result = base ** exponent
    except Exception as exc:
        raise evaluation_error(f'Call to "power()" resulted in an invalid number') from exc
    if isinstance(result, complex):
        raise evaluation_error('Call to "power()" resulted in an invalid number')
    return _valid_number(result, "power")


def _from_code_point(value: Any, to_integer) -> str:
    try:
        points = value if isinstance(value, list) else [value]
        return "".join(chr(to_integer(point)) for point in points)
    except Exception as exc:
        raise evaluation_error(f'Invalid code point: "{value}"') from exc


def _left(subject: Any, count: Any | None, to_integer) -> Any:
    num_entries = to_integer(count) if count is not None else 1
    if num_entries < 0:
        raise evaluation_error("left() requires a non-negative number of elements")
    source = get_value_of(subject)
    if isinstance(source, list):
        return source[:num_entries]
    text = list(_scalar_text(source))
    return "".join(text[:num_entries])


def _right(subject: Any, count: Any | None, to_integer) -> Any:
    num_entries = to_integer(count) if count is not None else 1
    if num_entries < 0:
        raise evaluation_error("right() count must be greater than or equal to 0")
    source = get_value_of(subject)
    if isinstance(source, list):
        return [] if num_entries == 0 else source[-num_entries:]
    if num_entries == 0:
        return ""
    text = list(_scalar_text(source))
    return "".join(text[-num_entries:])


def _mid(subject: Any, start: Any, length: Any, to_integer) -> Any:
    start_idx = to_integer(start)
    length_val = to_integer(length)
    source = get_value_of(subject)
    if start_idx < 0:
        raise evaluation_error("mid() requires a non-negative start position")
    if length_val < 0:
        raise evaluation_error("mid() requires a non-negative length parameter")
    if isinstance(source, list):
        return source[start_idx : start_idx + length_val]
    text = list(_scalar_text(source))
    return "".join(text[start_idx : start_idx + length_val])


def _debug_fn(args: list[Any], runtime, debug: list[str], to_integer) -> Any:
    arg = args[0]
    if len(args) > 1:
        display = args[1]
        if isinstance(display, dict) and display.get("jmespathType") == "Expref":
            debug.append(runtime.interpreter.visit(display, arg))
        else:
            debug.append(display)
    else:
        debug.append(_to_json(arg, 0, to_integer))
    return arg


def _if_function(args: list[Any], data: Any, interpreter) -> Any:
    condition = interpreter.visit(args[0], data)
    if get_type(condition) == TYPE_EXPREF:
        raise type_error("if() condition must not be an expression reference")
    return interpreter.visit(args[1], data) if to_boolean(condition) else interpreter.visit(args[2], data)


def _scalar_text(value: Any) -> str:
    unwrapped = get_value_of(value)
    return "" if unwrapped is None else str(unwrapped)


def _trim_spaces(value: Any) -> str:
    return " ".join(to for to in _scalar_text(value).split(" ") if to)


def _round_half_up(value: float, digits: int) -> float:
    precision = 10 ** digits
    return math.floor(value * precision + 0.5) / precision


def _substitute_eval(args: list[Any], to_integer) -> Any:
    def normalize_which(value: Any) -> Any:
        if isinstance(value, list):
            normalized = [normalize_which(item) for item in value]
            if any(item < 0 for item in _flatten(normalized)):
                raise evaluation_error("substitute() which parameter must be greater than or equal to 0")
            return normalized
        normalized = to_integer(value)
        if normalized < 0:
            raise evaluation_error("substitute() which parameter must be greater than or equal to 0")
        return normalized

    if len(args) > 3:
        args = args[:3] + [normalize_which(args[3])]
    return _evaluate(args, lambda a, b, c, d=-1: _substitute(a, b, c, d))


def _type_name(value: Any) -> str:
    lookup = {
        TYPE_NUMBER: "number",
        TYPE_ANY: "any",
        TYPE_STRING: "string",
        TYPE_ARRAY: "array",
        TYPE_OBJECT: "object",
        TYPE_BOOLEAN: "boolean",
        TYPE_EXPREF: "expression",
        TYPE_NULL: "null",
        TYPE_ARRAY_NUMBER: "array",
        TYPE_ARRAY_STRING: "array",
        TYPE_ARRAY_ARRAY: "array",
        TYPE_EMPTY_ARRAY: "array",
    }
    return lookup[get_type(value)]
