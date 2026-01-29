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

## See Also

- [Python Standards](python.md) - General Python coding standards
- [Backend Architecture](../../knowledge/backend/architecture.md) - Backend architecture overview
