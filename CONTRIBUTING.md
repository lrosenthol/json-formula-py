# Contributing

Thanks for contributing to `json-formula`.

## Development Setup

Create a local editable install with development dependencies:

```bash
python3 -m pip install -e .[dev]
```

If you prefer to install only the runtime package:

```bash
python3 -m pip install -e .
python3 -m pip install pytest wheel build twine
```

## Running Tests

Run the official conformance suite:

```bash
python3 -m pytest tests/test_official_suite.py -q
```

Run the whole test suite:

```bash
python3 -m pytest
```

Build and verify release artifacts:

```bash
python3 -m build
python3 -m twine check dist/*
```

## Project Expectations

- Keep the evaluator completely native to Python.
- Do not introduce a dependency on the upstream JavaScript runtime for
  execution.
- Use the vendored upstream implementation only as a behavioral reference.
- Prefer focused, spec-aligned fixes over broad behavior changes.
- Preserve compatibility with the official fixture corpus.

## Code Style

- Target Python 3.9+.
- Keep changes ASCII unless the file already requires Unicode.
- Prefer small, readable helpers over dense logic.
- Add comments sparingly and only where they clarify non-obvious behavior.

## Adding Or Changing Behavior

When changing evaluation behavior:

1. Add or update tests first when practical.
2. Run the official suite.
3. Verify both JSON mode and field-object mode still pass.
4. Document user-visible behavior changes in the README when appropriate.

## Reporting Issues

Useful bug reports usually include:

- the JSON Formula expression
- the input JSON document
- the expected result
- the actual result or exception
- the Python version in use

## License

By contributing, you agree that your contributions will be licensed under the
MIT License that covers this repository.
