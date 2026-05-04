# Copyright 2026 Adobe. All rights reserved.
# This file is licensed to you under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License. You may obtain a copy
# of the License at http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software distributed under
# the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR REPRESENTATIONS
# OF ANY KIND, either express or implied. See the License for the specific language
# governing permissions and limitations under the License.

"""Public API for the native Python JSON Formula engine."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterable, MutableSequence, Optional

from .runtime import Formula


_STRICT_NUMBER_RE = re.compile(r"^\s*(-|\+)?(\d*)(\.\d+)?(e(\+|-)?\d+)?\s*$", re.IGNORECASE)


def strict_string_to_number(value: str) -> float:
    if not _STRICT_NUMBER_RE.match(value):
        raise TypeError(f'Failed to convert "{value}" to number')
    converted = float(value)
    if converted != converted:
        raise TypeError(f'Failed to convert "{value}" to number')
    return converted


@dataclass
class JsonFormula:
    debug: Optional[MutableSequence[str]] = None
    custom_functions: Optional[dict[str, Any]] = None
    string_to_number: Any = strict_string_to_number
    _formula: Formula = field(init=False, repr=False)

    def __post_init__(self) -> None:
        debug = self.debug if self.debug is not None else []
        self._formula = Formula(debug, self.custom_functions or {}, self.string_to_number)
        self.debug = debug

    def search(
        self,
        expression: str,
        json_data: Any,
        globals: Optional[dict[str, Any]] = None,
        language: str = "en-US",
    ) -> Any:
        ast = self.compile(expression, (globals or {}).keys())
        return self.run(ast, json_data, language=language, globals=globals)

    def compile(self, expression: str, allowed_global_names: Optional[Iterable[str]] = None) -> dict[str, Any]:
        assert self.debug is not None
        self.debug[:] = []
        return self._formula.compile(expression, list(allowed_global_names or []))

    def run(
        self,
        ast: dict[str, Any],
        json_data: Any,
        language: str = "en-US",
        globals: Optional[dict[str, Any]] = None,
    ) -> Any:
        return self._formula.search(ast, json_data, globals or {}, language)


def json_formula(
    json_data: Any,
    globals: Optional[dict[str, Any]],
    expression: str,
    *,
    custom_functions: Optional[dict[str, Any]] = None,
    string_to_number: Any = strict_string_to_number,
    debug: Optional[MutableSequence[str]] = None,
    language: str = "en-US",
) -> Any:
    engine = JsonFormula(debug=debug, custom_functions=custom_functions, string_to_number=string_to_number)
    return engine.search(expression, json_data, globals or {}, language)
