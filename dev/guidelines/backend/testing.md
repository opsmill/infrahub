# Python Testing Standards

> Part of: `dev/guidelines/backend/` | Related: [Python Standards](python.md)

Testing standards for the Python backend.

## Test Organization

Tests are organized by type:

- **Unit tests** (`tests/unit/`): No external dependencies, only file access
- **Component tests** (`tests/component/`): Small scope but may require database access
- **Functional tests** (`tests/functional/`): Multi-component tests running in a single thread/process. Async tasks execute inline without separate workers.
- **Integration tests** (`tests/integration/`): Require Neo4j via testcontainers
- **Integration Docker tests** (`tests/integration_docker/`): Integration tests that run in a full environment with containers

Note that at some point the current integration tests will be merged with the functional tests and the `tests/integration_docker` tests will move to `tests/integration`.

Test files mirror source structure: `infrahub/core/node.py` → `tests/unit/core/test_node.py`

## Test Schemas

Many tests require schemas to be loaded before they can run. Over time this has led to duplicated schema definitions scattered across test files. To reduce duplication and ease maintenance, shared helper schemas are available in [`tests/helpers/schema/`](../../../backend/tests/helpers/schema/).

### Available helpers

The module provides individual node/generic schemas (`CAR`, `DEVICE`, `TAG`, `PERSON`, etc.) as well as pre-composed `SchemaRoot` bundles (`CAR_SCHEMA`, `DEVICE_SCHEMA`, `LOCATION_SCHEMA`, `SNOW_TICKET_SCHEMA`, etc.). A `load_schema` helper function handles registering a schema in the branch registry during tests.

### Guidelines

1. **Check existing helpers first.** Before defining a new schema in a test file, look at the schemas already available in `tests/helpers/schema/`. An existing schema may already cover your needs.

2. **Derive from helpers with `deepcopy`.** When you need a schema that is close to an existing helper but requires small additions or modifications, deep-copy the helper and apply your changes instead of writing a new schema from scratch:

   ```python
   from copy import deepcopy

   from infrahub.core.schema import AttributeSchema
   from tests.helpers.schema import CAR

   car_with_mileage = deepcopy(CAR)
   car_with_mileage.attributes.append(
       AttributeSchema(name="mileage", kind="Number")
   )
   ```

   This avoids modifying the shared helper (which would risk breaking other tests) while keeping the test schema close to the canonical definition.

3. **Only create new helpers for broadly useful schemas.** If a schema is only needed by a single test file, keep it local to that file. Promote a local schema to `tests/helpers/schema/` only when multiple test modules would benefit from sharing it.

4. **Never modify an existing helper schema to satisfy a single test.** Changes to shared schemas affect every test that uses them. If an existing helper almost fits but not quite, use `deepcopy` as shown above.

## Dataclass Test Case Pattern

For parametrized tests with multiple scenarios, use dataclasses to define test cases. This pattern provides type safety, readable test IDs, and clear separation between test data and test logic.

### Basic Structure

```python
from dataclasses import dataclass

import pytest


@dataclass
class MyFunctionTestCase:
    name: str
    """Descriptive name for the test scenario (used as test ID)."""

    input_value: str
    """The input to pass to the function."""

    expected: bool
    """The expected return value."""


MY_FUNCTION_TEST_CASES: list[MyFunctionTestCase] = [
    MyFunctionTestCase(
        name="empty_string_returns_false",
        input_value="",
        expected=False,
    ),
    MyFunctionTestCase(
        name="valid_string_returns_true",
        input_value="hello",
        expected=True,
    ),
]


@pytest.mark.parametrize(
    "test_case",
    [pytest.param(tc, id=tc.name) for tc in MY_FUNCTION_TEST_CASES],
)
def test_my_function(test_case: MyFunctionTestCase) -> None:
    """Test that my_function handles various inputs correctly."""
    result = my_function(value=test_case.input_value)
    assert result == test_case.expected
```

### Guidelines

1. **Always include a `name` field** as the first field in the dataclass. This becomes the test ID in pytest output, i.e. a meaningful name makes the output easier to read.

2. **Use descriptive names** that explain the scenario: `empty_dict_returns_false`, `nested_key_found_at_second_level`, `invalid_input_raises_error`.

3. **Document fields with inline docstrings** (per Python standards):

   ```python
   @dataclass
   class QueryTestCase:
       name: str
       """Descriptive name for the test scenario."""

       query: str
       """The Cypher query to execute."""

       params: dict[str, Any]
       """Parameters to pass to the query."""

       expected_count: int
       """Expected number of results."""
   ```

4. **Define test cases as module-level constants** with uppercase names and type hints:

   ```python
   QUERY_TEST_CASES: list[QueryTestCase] = [...]
   ```

5. **Place test case lists before the test function** that uses them.

6. **Use keyword arguments** when constructing test cases for clarity:

   ```python
   # Good
   MyTestCase(
       name="scenario_one",
       input_value="test",
       expected=True,
   )

   # Bad
   MyTestCase("scenario_one", "test", True)
   ```

### Complex Test Cases

For tests with complex inputs or expected outputs, the dataclass can contain nested objects:

```python
from dataclasses import dataclass

from infrahub.core.schema import NodeSchema, SchemaRoot


@dataclass
class SchemaValidationTestCase:
    name: str
    """Descriptive name for the test scenario."""

    schema: SchemaRoot
    """The schema to validate."""

    expected_errors: list[str]
    """List of expected validation error messages."""


SCHEMA_VALIDATION_TEST_CASES: list[SchemaValidationTestCase] = [
    SchemaValidationTestCase(
        name="missing_required_field",
        schema=SchemaRoot(
            nodes=[
                NodeSchema(
                    namespace="Test",
                    name="Device",
                    attributes=[],
                )
            ]
        ),
        expected_errors=["Node TestDevice requires at least one attribute"],
    ),
]
```

### When to Use This Pattern

Use the dataclass test case pattern when:

- Testing a function with multiple input/output scenarios
- Test cases share a common structure
- You want readable test IDs in pytest output
- The test logic is the same but data varies

For simpler cases with only 2-3 scenarios, standard `@pytest.mark.parametrize` with tuples may be sufficient:

```python
@pytest.mark.parametrize(
    ("input_value", "expected"),
    [
        ("", False),
        ("hello", True),
    ],
)
def test_simple_function(input_value: str, expected: bool) -> None:
    assert simple_function(input_value) == expected
```

## Caution against mocking

Avoid using `unittest.mock` or `pytest-mock` to patch functions, methods, or modules. Mocking creates a false sense of security: tests pass while the actual integration may be broken. When the real implementation changes, mocked tests continue to pass, hiding regression bugs.

### Prefer adapters and protocols

Instead of mocking, design code with explicit boundaries using adapters, interfaces, or protocols. This allows swapping implementations for testing without patching internals.

**Example:** The message bus uses this pattern:

- Production: [rabbitmq.py](../../../backend/infrahub/services/adapters/message_bus/rabbitmq.py) - Real RabbitMQ implementation
- Testing: [message_bus.py](../../../backend/tests/adapters/message_bus.py) - `BusRecorder` and `BusSimulator` test implementations

Both implement the same `InfrahubMessageBus` protocol. Tests inject the test adapter—no mocking required, and refactoring the RabbitMQ implementation won't silently break tests.

### When mocking seems necessary

If you find yourself wanting to mock:

1. **Refactor for testability** - Extract the dependency behind an interface
2. **Move up the test pyramid** - A component test requiring extensive mocking to simulate an end-to-end flow is often better written as an integration or functional test
3. **Question the test scope** - If testing requires mocking half the system, the unit under test may be too large

### Acceptable exceptions

- External HTTP APIs with no test mode (use `responses` or `httpx_mock` sparingly)
- Time-dependent behavior (`freezegun`)

Even in these cases, prefer adapter patterns when the dependency is used widely.

## Exception Testing

When testing that code raises an exception, use the `match` parameter of `pytest.raises` to validate the error message:

```python
# Good - use match parameter for message validation
with pytest.raises(PoolExhaustedError, match=r"no more addresses available"):
    allocate_from_pool(pool_id=exhausted_pool.id)

# Bad - manual assertion on exception message
with pytest.raises(PoolExhaustedError) as exc_info:
    allocate_from_pool(pool_id=exhausted_pool.id)

assert "no more addresses available" in exc_info.value.message
```

The `match` parameter accepts a regular expression pattern and is more concise. Use `r"..."` raw strings to avoid escaping issues.

## GraphQL Result Assertions

When testing GraphQL mutations or queries that return errors, always assert on the **specific error message** using an equality check. Vague assertions hide regressions — if the error changes (e.g., a different validation fires first), the test keeps passing silently.

```python
# Bad - only checks that some error occurred
assert result.errors

# Bad - a substring check passes for any error that mentions the ID
assert TEMPLATE_ID in str(result.errors[0])

# Bad - slightly better but still a substring match, any error containing
# this text passes even if the overall message changed
assert f"The template requested {{'id': '{TEMPLATE_ID}'}} was not found." in str(result.errors[0])

# Good - exact match on the error message
assert result.errors
assert str(result.errors[0].message) == f"The template requested {{'id': '{TEMPLATE_ID}'}} was not found."
```

Use `==` rather than `in` to compare error messages. An exact match ensures the test fails when the error wording changes, keeping assertions tightly coupled to the expected behavior.

## See Also

- [Python Standards](python.md) - General Python coding standards
- [Backend Architecture](../../knowledge/backend/architecture.md) - Backend architecture overview
