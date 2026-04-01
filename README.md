# json-formula

`json-formula` is a completely native Python implementation of the
[Adobe JSON Formula specification](https://opensource.adobe.com/json-formula/).
It includes a lexer, Pratt parser, runtime, built-in function library, and
test harness validated against Adobe's official conformance fixtures.

The package does not rely on JavaScript for evaluation. The upstream
JavaScript implementation is vendored only as reference material and for
fixture provenance.

## Features

- Native Python parser and evaluator
- One-shot and compiled-expression APIs
- Official Adobe fixture-suite validation with `pytest`
- Support for both normal JSON data and the field-object execution mode used by
  the upstream suite
- Typed exception classes for syntax, type, function, and evaluation failures

## Installation

Install from a checkout:

```bash
python3 -m pip install -e .
```

Install development dependencies:

```bash
python3 -m pip install -e .[dev]
```

If you are setting up the environment manually, install `pytest` and `wheel`
alongside the editable package:

```bash
python3 -m pip install -e .
python3 -m pip install pytest wheel
```

## Quick Start

```python
from json_formula import JsonFormula

jf = JsonFormula()

data = {
    "items": [
        {"desc": "pens", "quantity": 2, "price": 3.23},
        {"desc": "pencils", "quantity": 4, "price": 1.34},
    ]
}

result = jf.search("sum(items[*].price * items[*].quantity)", data)
assert result == 11.82
```

## Public API

### `JsonFormula`

Primary engine class.

```python
from json_formula import JsonFormula

jf = JsonFormula()
result = jf.search("foo.bar", {"foo": {"bar": 3}})
assert result == 3
```

Constructor options:

- `debug`: mutable sequence that collects debug messages generated during parse
  and evaluation
- `custom_functions`: mapping of custom function definitions to seed the runtime
- `string_to_number`: custom string-to-number conversion function

### `search(expression, json_data, globals=None, language="en-US")`

Parses and evaluates an expression in one step.

```python
from json_formula import JsonFormula

jf = JsonFormula()
days = ["Mon", "Tue", "Wed"]

result = jf.search(
    "value($days, num)",
    {"num": 2},
    globals={"$days": days},
)

assert result == "Wed"
```

### `compile(expression, allowed_global_names=None)`

Parses an expression and returns an AST suitable for repeated execution.

```python
from json_formula import JsonFormula

jf = JsonFormula()
ast = jf.compile("sum(items[*].price)", allowed_global_names=["$tax"])
```

### `run(ast, json_data, language="en-US", globals=None)`

Runs a previously compiled AST.

```python
from json_formula import JsonFormula

jf = JsonFormula()
ast = jf.compile("sum(items[*].price)")

result = jf.run(ast, {"items": [{"price": 1.5}, {"price": 2.5}]})
assert result == 4.0
```

### Functional helper

The package also exposes `json_formula(...)` for simple one-shot usage.

```python
from json_formula import json_formula

result = json_formula({"a": 1}, {}, "a")
assert result == 1
```

## Exceptions

The package exports:

- `JsonFormulaError`
- `SyntaxError`
- `TypeError`
- `FunctionError`
- `EvaluationError`

Example:

```python
from json_formula import JsonFormula, SyntaxError

jf = JsonFormula()

try:
    jf.search("foo[", {"foo": [1, 2, 3]})
except SyntaxError as exc:
    print(exc)
```

## Testing

Run the official-suite harness:

```bash
python3 -m pytest tests/test_official_suite.py -q
```

Run all tests:

```bash
python3 -m pytest
```

The official-suite harness uses the fixture corpus under
[tests/fixtures/official](/Users/lrosenth/Development/json-formula-py/tests/fixtures/official)
and validates both:

- standard JSON execution
- field-object execution compatibility

At the time of this update, the native engine passes the full official suite:

```text
4240 passed
```

## Project Layout

- [src/json_formula](/Users/lrosenth/Development/json-formula-py/src/json_formula): package source
- [tests/test_official_suite.py](/Users/lrosenth/Development/json-formula-py/tests/test_official_suite.py): official-suite pytest harness
- [tests/fixtures/official](/Users/lrosenth/Development/json-formula-py/tests/fixtures/official): upstream JSON conformance fixtures
- [CONTRIBUTING.md](/Users/lrosenth/Development/json-formula-py/CONTRIBUTING.md): contribution guide
- [LICENSE](/Users/lrosenth/Development/json-formula-py/LICENSE): MIT license for this Python project
- [LICENSE.upstream](/Users/lrosenth/Development/json-formula-py/LICENSE.upstream): upstream Adobe license notice
- [NOTICE.upstream.txt](/Users/lrosenth/Development/json-formula-py/NOTICE.upstream.txt): upstream attribution

## Relationship To The Upstream Project

This project implements the JSON Formula specification in Python. The upstream
Adobe JavaScript implementation and fixture suite were used for specification
validation and behavioral comparison, but not for runtime execution.

## License

This Python project is distributed under the MIT License. See
[LICENSE](/Users/lrosenth/Development/json-formula-py/LICENSE).

The vendored upstream JavaScript reference files retain their original license
and notices in [LICENSE.upstream](/Users/lrosenth/Development/json-formula-py/LICENSE.upstream)
and [NOTICE.upstream.txt](/Users/lrosenth/Development/json-formula-py/NOTICE.upstream.txt).
