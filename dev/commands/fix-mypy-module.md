---
description: Find and fix mypy typing violations for a specific module override in pyproject.toml
allowed-tools: Bash(uv run mypy:*), Read, Edit, Glob
argument-hint: <module-name e.g., infrahub.core.attribute> [error-code e.g., arg-type]
---

Fix mypy typing violations for module: $ARGUMENTS

**Important**: The argument should be either:

1. A module name that has a `[[tool.mypy.overrides]]` section in pyproject.toml (e.g., `infrahub.core.attribute`)
2. A module name followed by a specific error code to fix (e.g., `infrahub.core.attribute arg-type`)

## First Step (Before All Else)

1. Read `pyproject.toml` and extract all modules that have `[[tool.mypy.overrides]]` sections with `disable_error_code` lists
2. Parse the user's argument to extract the module name and optional error code
3. If the module doesn't match any override with disabled error codes, list the available modules and ask for clarification before proceeding

## Context

The pyproject.toml file contains mypy configuration with module-specific overrides in `[[tool.mypy.overrides]]` sections. Each override may have:

- `module` - The module pattern this override applies to (e.g., `infrahub.core.attribute`)
- `disable_error_code` - A list of mypy error codes that are ignored for this module
- Other settings like `disallow_untyped_defs`

The goal is to fix typing violations so that error codes can be removed from `disable_error_code` lists, improving type safety.

## Common Mypy Error Codes

- `arg-type` - Argument has incompatible type
- `assignment` - Incompatible types in assignment
- `attr-defined` - Has no attribute
- `call-overload` - No overload variant matches
- `index` - Invalid index type
- `misc` - Miscellaneous errors
- `no-redef` - Name already defined
- `no-untyped-def` - Function is missing type annotations
- `operator` - Unsupported operand types
- `override` - Signature incompatible with supertype
- `return` - Missing return statement
- `return-value` - Incompatible return value type
- `union-attr` - Item of union has no attribute
- `var-annotated` - Need type annotation for variable

## Steps to Follow

1. **Parse the arguments**: Determine if we have:
   - Just a module name (fix all disabled error codes for that module)
   - A module name + specific error code (fix only that error code)

2. **Locate the override section**: Read pyproject.toml and find the `[[tool.mypy.overrides]]` section for the specified module. Note:
   - The exact `disable_error_code` list
   - Any other settings in that override section
   - If no override exists, inform the user

3. **Determine the file(s) to check**: The module name maps to a file or directory.

   **Module Path Resolution:**

   | Module pattern | File/Directory |
   | -------------- | -------------- |
   | `infrahub.core.attribute` | `backend/infrahub/core/attribute.py` OR `backend/infrahub/core/attribute/__init__.py` |
   | `infrahub.core.node` | `backend/infrahub/core/node/__init__.py` (package) |
   | `infrahub.core.node.*` | `backend/infrahub/core/node/` (entire directory) |
   | `tests.integration.*` | `backend/tests/integration/` (entire directory) |

   **Resolution algorithm:**
   1. Convert module to path: `backend/{module.replace('.', '/')}`
   2. If pattern ends with `.*`, target the entire directory
   3. Otherwise, check if `{path}.py` exists; if not, check `{path}/__init__.py`

4. **Find current violations**: To see what errors would appear if the error codes were enabled:

   a. **Temporarily edit pyproject.toml**: Remove the target error code(s) from the module's `disable_error_code` list

   b. **Run mypy on the module**:

   ```bash
   uv run mypy --show-error-codes backend/infrahub/path/to/module.py
   ```

   c. **Capture the errors**: Note all violations related to the error code(s) being fixed

   d. **Restore pyproject.toml**: Revert the temporary change before making code fixes

   If fixing all error codes, remove them one at a time to understand the scope of each.

5. **Present findings**: Before making any changes, summarize:
   - Number of violations per error code
   - Types of violations found
   - Estimated complexity of the fix
   - Whether the override section should be removed entirely or just modified

   Then ask for approval to proceed with the fixes.

6. **Fix the violations**: For each affected file:
   - Add proper type annotations
   - Fix type mismatches
   - Add appropriate type: ignore comments ONLY when the fix would be too complex or break functionality
   - Use typing constructs like `TypeVar`, `overload`, etc. where appropriate
   - Maintain code functionality and readability

7. **Update pyproject.toml**:
   - If fixing a specific error code: Remove it from the `disable_error_code` list
   - If fixing all error codes and the list becomes empty: Remove the entire `[[tool.mypy.overrides]]` section
   - If only `disallow_untyped_defs = false` remains (for test files), keep the section

8. **Validate**: Run mypy on the module to confirm the fix is complete:

   ```bash
   uv run mypy --show-error-codes backend/infrahub/path/to/module.py
   ```

   **Success criteria:**
   - The command exits with code 0
   - No errors related to the fixed error codes appear
   - Some unrelated warnings may appear if they're from other still-disabled error codes—these are acceptable

9. **Run full mypy check**: Verify no regressions with:

   ```bash
   uv run invoke backend.mypy
   ```

10. **Run relevant tests**: If the changes are non-trivial, run related tests to ensure nothing is broken

## Important Notes

- Do NOT add blanket `# type: ignore` comments - be specific with error codes if required, the goal should be to completely avoid any ignores
- If a module has many violations (>20 for a single error code), fix in batches of ~10. After each batch, validate and ask: "Fixed N of M violations. Continue with the next batch?"
- Some typing fixes may require refactoring - be cautious and test
- Preserve code functionality - the goal is type safety, not rewriting
- If validation fails after fixes, investigate before proceeding
- Some test-related overrides (`tests.*`) may be intentionally lenient - confirm before changing

## Common Fix Patterns

### `union-attr` - Use isinstance narrowing

```python
# Before
value.some_method()  # error: Item "None" of "Optional[X]" has no attribute "some_method"

# After
if value is not None:
    value.some_method()

# Or use assert for cases where None is unexpected
assert value is not None
value.some_method()
```

### `arg-type` - Widen parameter type or cast value

```python
# Option 1: Widen the parameter type in the function signature
def process(value: str | int) -> None: ...

# Option 2: Add runtime type check
if isinstance(value, str):
    process(value)
```

### `return-value` - Ensure all paths return correct type

```python
# Before
def get_value() -> str:
    if condition:
        return "value"
    # Missing return - implicitly returns None!

# After
def get_value() -> str:
    if condition:
        return "value"
    return ""  # Explicit default

# Or raise if the missing path is an error
def get_value() -> str:
    if condition:
        return "value"
    raise ValueError("Condition was not met")
```

### `assignment` - Fix type mismatch in assignment

```python
# Before
result: str = some_func()  # error: Incompatible types (got Optional[str])

# After - Option 1: Widen the annotation
result: str | None = some_func()

# After - Option 2: Provide default
result: str = some_func() or ""

```

### `attr-defined` - Check attribute exists or fix type

```python
# Before
obj.some_attr  # error: "BaseClass" has no attribute "some_attr"

# After - Option 1: isinstance check
if isinstance(obj, SpecificClass):
    obj.some_attr

# After - Option 2: hasattr check (less preferred)
if hasattr(obj, "some_attr"):
    obj.some_attr

# After - Option 3: Fix the type annotation upstream
def get_obj() -> SpecificClass:  # Not BaseClass
    ...
```

### `override` - Match parent signature exactly

```python
# Before
class Child(Parent):
    def method(self, x: int) -> str:  # error: signature incompatible with Parent
        ...

# After - Match parent signature, then narrow internally
class Child(Parent):
    def method(self, x: int | str) -> str | None:  # Matches Parent.method
        if isinstance(x, int):
            ...
```
