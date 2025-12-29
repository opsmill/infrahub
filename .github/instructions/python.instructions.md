---
applyTo: '**/*.py'
---

# Python rules

- Use type hints for all function parameters and return values
- Use Async whenever possible
- Use `async def` for asynchronous functions
- Use `await` for asynchronous calls
- Use Pydantic models for dataclasses

## Formatting and Linting

The project is using Use ruff and mypy for type checking and validations.

you can format all python files by running `uv run invoke format`
and you can validate that all files are formatted correctly by running `uv run invoke lint`
