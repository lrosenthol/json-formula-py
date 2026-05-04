# Copyright 2026 Adobe. All rights reserved.
# This file is licensed to you under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License. You may obtain a copy
# of the License at http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software distributed under
# the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR REPRESENTATIONS
# OF ANY KIND, either express or implied. See the License for the specific language
# governing permissions and limitations under the License.

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import pytest

from json_formula import JsonFormula
from json_formula.object_model import create_form
from json_formula.utils import json_clone


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "official"
SUITES = [
    "basic",
    "boolean",
    "current",
    "docSamples",
    "escape",
    "filters",
    "functions",
    "identifiers",
    "indices",
    "literal",
    "multiselect",
    "pipe",
    "slice",
    "specSamples",
    "syntax",
    "tests",
    "unicode",
    "wildcard",
]

HELPERS = [
    """register("_summarize",
      &reduce(
        @,
        &merge(accumulated, fromEntries([[current, 1 + value(accumulated, current)]])),
        fromEntries(map(@, &[@, 0]))
      )
    )""",
    """register(
      "_localDate",
      &split(@, "-") | datetime(@[0], @[1], @[2]))""",
    'register("_product", &@[0] * @[1])',
]


def load_suite(name: str) -> list[dict[str, Any]]:
    return json.loads((FIXTURE_DIR / f"{name}.json").read_text())


def iter_cases():
    for suite_name in SUITES:
        for suite in load_suite(suite_name):
            given = suite["given"]
            suite_comment = suite.get("comment", "")
            for case in suite["cases"]:
                label = " -> ".join(part for part in (case.get("comment") or suite_comment, case["expression"]) if part)
                if not case.get("fieldsOnly"):
                    yield pytest.param("json", suite_name, given, case, id=f"{suite_name}:json:{label}")
                yield pytest.param("fields", suite_name, given, case, id=f"{suite_name}:fields:{label}")


@pytest.fixture
def engine() -> JsonFormula:
    jf = JsonFormula()
    for helper in HELPERS:
        jf.search(helper, {})
    return jf


def resolve_data(engine: JsonFormula, given: Any, case: dict[str, Any]) -> Any:
    override = case.get("data")
    if override is None:
        return given
    if isinstance(override, str):
        return engine.search(override, given, {})
    return override


def assert_json_equal(actual: Any, expected: Any) -> None:
    if isinstance(actual, float) and isinstance(expected, (int, float)):
        assert math.isclose(actual, float(expected), rel_tol=1e-6, abs_tol=1e-6)
        return
    if isinstance(actual, list) and isinstance(expected, list):
        assert len(actual) == len(expected)
        for left, right in zip(actual, expected):
            assert_json_equal(left, right)
        return
    if isinstance(actual, dict) and isinstance(expected, dict):
        assert actual.keys() == expected.keys()
        for key in actual:
            assert_json_equal(actual[key], expected[key])
        return
    assert actual == expected


@pytest.mark.parametrize(("mode", "suite_name", "given", "case"), list(iter_cases()))
def test_official_suite(mode: str, suite_name: str, given: Any, case: dict[str, Any], engine: JsonFormula) -> None:
    data = resolve_data(engine, given, case)
    root = create_form(data) if mode == "fields" else data
    globals_obj = {
        "$days": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
        "$": 42,
        "$$": 43,
        "$form": data,
    }
    language = case.get("language", "en-US")

    try:
        result = engine.search(case["expression"], root, globals_obj, language)
    except Exception as exc:  # noqa: BLE001
        expected = case.get("error")
        if expected is None:
            raise
        assert exc.__class__.__name__ == expected
        return

    if "error" in case:
        pytest.fail(f"expected {case['error']} but got success with result={result!r}")

    if mode == "fields":
        result = json_clone(result)

    expected_result = case.get("result")
    assert_json_equal(result, expected_result)
