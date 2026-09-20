---
paths:
  - "backend/**/*.py"
  - "python_testcontainers/**/*.py"
---

# Python module layout

Applies when adding code to existing modules or deciding where new code lives.

## constants.py holds constants only

Do not put functions or classes in a file named `constants.py` — only module-level constant values (plain literals, enums, frozen containers). A value that must be computed, read from the environment, or resolved at runtime is not a constant; give it a home in a purpose-named module (e.g. `limits.py`, `settings.py`) instead.

Why: readers grep and import from `constants.py` expecting inert values with no behavior and no import-time or call-time side effects. A function hiding there muddies that contract and gets overlooked when reasoning about runtime behavior.

If the value genuinely never changes at runtime, prefer an actual constant over a function returning one.

## Imports at the top

Keep imports at the top of the module. Do not import inside functions, methods, or classes. Ruff enforces this (`PLC0415`).

A function-local import is acceptable only to defer an optional or heavy dependency that must not load on every import; mark it `# noqa: PLC0415` with the reason. It does not fix an import cycle: a cycle means the module depends on a layer above it, so depend on the narrower interface it actually uses, split a union parameter into one typed slot per case, or move the helper next to its caller (`dev/guidelines/backend/python.md`, Imports).
