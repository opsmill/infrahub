---
paths:
  - "backend/**/*.py"
  - "python_testcontainers/**/*.py"
---

# Python module layout

Applies when adding code to existing modules or deciding where new code lives.

- A file named `constants.py` holds only module-level constant values: no functions, no classes, and nothing computed, read from the environment, or resolved at runtime.
- Keep imports at the top of the module; a function-local import is acceptable only to break a genuine circular import or to defer an optional or heavy dependency, and carries `# noqa: PLC0415` with a short reason.

Full reference: `dev/guidelines/backend/python.md` §"Module layout".
