---
paths:
  - "**/*.py"
---

# Python typing discipline

Applies to all Python, production and tests. Full reference: `dev/guidelines/backend/typing.md`.

## Suppressions are tech debt, not a tool

The mypy `disable_error_code` blocks and the `[[tool.ty.overrides]]` in `pyproject.toml` are existing tech debt, removed rule-by-rule. Treat each as a defect, never a pattern to copy.

- Do **not** add a new module/directory ignore, and do **not** extend an existing ignore list to cover a violation your change introduces.
- Do **not** add a new inline `# type: ignore` / `# ty: ignore` to silence a new violation.
- If your change trips a checker, fix the code — do not silence it.

Two narrow exceptions:

- A linter/type-checker **version upgrade** introduces new rules the codebase has not yet met. Grandfather those as a scoped, commented step, then burn them down.
- Re-enabling a previously-disabled rule for a module, where a scoped `# type: ignore[code]  # reason` grandfathers unrelated pre-existing violations (a net reduction, per `typing.md`). This never applies to a new violation.

## Fix the type, don't discard it

When the checker warns, find the approach that is actually correct — a Pydantic-native shape, a proper model/field type, or `isinstance` narrowing — rather than defeating the check.

- **No `cast()`.** It asserts a type without verifying it, turning type checking off exactly where a bug would hide. Narrow with a positive `isinstance` that returns the value instead — a `cast()` that only "records" what a check above established is still a `cast()`, and when the real check trips the checker in files you did not touch, root-cause that (usually an import) rather than falling back.
- **Prefer `isinstance` over `getattr()`.** `getattr(obj, "x", default)` hides the read from the checker and from grep. Narrow with `isinstance` (cover the whole family carrying the attribute) or use the typed, named accessor.
