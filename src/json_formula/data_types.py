# Copyright 2026 Adobe. All rights reserved.
# This file is licensed to you under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License. You may obtain a copy
# of the License at http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software distributed under
# the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR REPRESENTATIONS
# OF ANY KIND, either express or implied. See the License for the specific language
# governing permissions and limitations under the License.

"""Type constants used by JSON Formula functions and coercion logic."""

from __future__ import annotations


TYPE_NUMBER = 0
TYPE_ANY = 1
TYPE_STRING = 2
TYPE_ARRAY = 3
TYPE_OBJECT = 4
TYPE_BOOLEAN = 5
TYPE_EXPREF = 6
TYPE_NULL = 7
TYPE_ARRAY_NUMBER = 8
TYPE_ARRAY_STRING = 9
TYPE_ARRAY_ARRAY = 10
TYPE_EMPTY_ARRAY = 11

TYPE_NAME_TABLE = {
    TYPE_NUMBER: "number",
    TYPE_ANY: "any",
    TYPE_STRING: "string",
    TYPE_ARRAY: "array",
    TYPE_OBJECT: "object",
    TYPE_BOOLEAN: "boolean",
    TYPE_EXPREF: "expression",
    TYPE_NULL: "null",
    TYPE_ARRAY_NUMBER: "Array<number>",
    TYPE_ARRAY_STRING: "Array<string>",
    TYPE_ARRAY_ARRAY: "Array<array>",
    TYPE_EMPTY_ARRAY: "array",
}
