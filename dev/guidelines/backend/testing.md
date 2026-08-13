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

**Pick the cheapest tier the logic actually needs.** If the unit under test operates purely on in-memory inputs (a `SchemaBranch`, a dataclass, a pure function), write a unit test in `tests/unit/` without database fixtures — do not default to a component test just because nearby tests use one. Reach for the database (component) or a container (integration/integration_docker) only when the behavior genuinely depends on it.

Note that at some point the current integration tests will be merged with the functional tests and the `tests/integration_docker` tests will move to `tests/integration`.

### Running integration_docker tests locally

Repo-based `tests/integration_docker/` tests build throwaway git repositories with dulwich (`porcelain.commit`), which honors your global `commit.gpgsign` setting. If you sign commits and the `gpg` Python bindings (gpgme) are not installed — common on macOS — repository setup fails with a misleading `ModuleNotFoundError: No module named 'gpg'`. That takes down every repo-based test plus any test that depends on the repo, showing up as cascading, confusing assertion failures.

These tests never need signed commits. Disable signing for the run by pointing git's config at `/dev/null`:

```bash
GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null uv run pytest backend/tests/integration_docker/<file>
```

With an empty config `commit.gpgsign` defaults to off, and dulwich falls back to your OS username/host for the commit author, so no `[user]` block is needed. CI does not sign commits, so this only affects local runs.

Test files mirror source structure: `infrahub/core/node.py` → `tests/unit/core/test_node.py`

## Test Documentation

Tests are behavioral specifications. Write them to describe **what the system should do**, not which bug prompted the test.

- **Do not reference issue numbers, GitHub URLs, or Jira tickets** in test code (names, comments, or docstrings). The git history links commits to issues.
- **Do not describe which bug a test prevents.** Describe the expected behavior instead.

## What not to test

Every test costs maintenance. Before adding one, ask whether it actually exercises behavior the project owns.

Skip tests that only assert third-party behavior:

- **Pydantic field constraints** (`ge`, `le`, `min_length`, `max_length`, etc.) — these are exercised by Pydantic's own test suite. Asserting that `Field(ge=1)` rejects `0` tests Pydantic, not us.
- **Pure assignment round-trips** — constructing a model with a value and asserting the attribute reads back the same value tests Python, not our code.
- **`SettingsConfigDict` plumbing** — asserting that an `env_prefix` exists or that `env_nested_delimiter` is set tests Pydantic Settings configuration, not behavior. Test the behavior you care about (an env var resolves to the right field) instead.
- **Plain `Enum` value checks** — asserting `MyEnum.FOO.value == "foo"` only tests that the enum literal matches itself.

Skip tests that test the framework rather than our integration:

- A test that only asserts a FastAPI route appears in `router.routes` duplicates `APIRouter`'s own contract — write it only when the registration goes through non-trivial conditional logic.
- A test that only asserts a Pydantic model has a particular field duplicates the type system.

A useful rule of thumb: if the test would still pass after we delete our implementation and reinstall the library, the test belongs to the library, not us.

**The exception is a bound that encodes a domain invariant.** `Field(ge=1)` on a multiplier that must never shrink the value it scales is not arbitrary tuning — it is a rule about how the feature behaves, and deleting it changes behavior with nothing failing. Assert those, but write the test against the invariant rather than the mechanism: name it for the rule, not for the constraint (`test_<what must hold>`, not `test_field_rejects_zero`), cover the boundary value that must stay legal, and add a test that the **shipped defaults** satisfy the invariant. Cross-field `model_validator` logic is ours outright and always warrants a test.

## Async tests

The project sets `asyncio_mode = "auto"` in `pyproject.toml`, so any `async def test_*` function is automatically driven by `pytest-asyncio`. **Do not** wrap async code in `asyncio.run(...)` inside synchronous tests — declare the test function `async` and `await` directly:

```python
# Good
async def test_returns_config() -> None:
    cfg = await get_config()
    assert cfg.ldap.enabled is False

# Bad — wraps the event loop unnecessarily
def test_returns_config() -> None:
    cfg = asyncio.run(get_config())
    assert cfg.ldap.enabled is False
```

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

## Pin settings the test depends on

`config.SETTINGS` is populated from `INFRAHUB_*` environment variables at process start, so values exported in the developer's shell leak into the test process. Any test whose behavior depends on a settings field must pin it in a save/restore fixture (set the value, `yield`, restore the original) — see `import_every_remote_branch` in `backend/tests/integration/git/conftest.py`. Never assume a field holds its default.

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

Two doubles are worth writing for any injected collaborator. A **recording** double — like `BusRecorder` — keeps what crossed the boundary, in order, so the test asserts the exact calls and values rather than "was called". A **failing** double raises on every call, to test the path a `Mock` never exercises: that a broken collaborator is handled the way the code claims — the operation still completes, state is intact, and anything queued behind it still runs. Keep both in the shared adapters package or a `helpers.py` beside the test package rather than redefining them per file.

### When mocking seems necessary

If you find yourself wanting to mock:

1. **Refactor for testability** - Extract the dependency behind an interface
2. **Move up the test pyramid** - A component test requiring extensive mocking to simulate an end-to-end flow is often better written as an integration or functional test
3. **Question the test scope** - If testing requires mocking half the system, the unit under test may be too large

### Acceptable exceptions

- External HTTP APIs with no test mode (use `responses` or `httpx_mock` sparingly)
- Prefect's `get_run_logger` when calling a `.fn` outside a flow context — patch it to return a stdlib `logging.getLogger(...)` so `caplog` can capture output. See [Backend Testing — Logging](../../knowledge/backend/testing.md#logging-use-caplog-instead-of-mocking-get_run_logger) for the pattern.

Even in these cases, prefer adapter patterns when the dependency is used widely.

### Time: inject a clock, don't freeze one

<!-- Extracted from specs/ifc-2886-priority-api-backpressure on 2026-07-26 -->

Time-dependent logic takes its clock as a constructor argument — a `Callable[[], float]`
defaulting to `time.monotonic` — and the test passes a fake it advances by hand. Do not reach for
`freezegun` (it is not a project dependency) and never `sleep()` in a test to let time pass.

```python
class RetryAfterPolicy:
    def __init__(self, *, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
```

```python
class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds
```

This keeps the unit under test a pure function of `(input, clock)`, so a state machine whose
behavior depends on elapsed time is tested exactly — cross an interval boundary, assert the
transition — with no wall-clock flakiness and no patching. Duration is a parameter of the logic,
not an ambient fact; treat it like any other injected collaborator (see
[Backend Component Design](../../../.agents/rules/backend-component-design.md)).

Use monotonic time for durations. Wall-clock time (`datetime.now`) is for timestamps that get
stored or displayed, and it can jump backwards.

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

## Assert exact expectations

The exact-match principle above is not limited to error messages — it applies to every assertion. A loose assertion passes for the wrong reason and hides regressions.

- **Assert the exact collection, not a subset or membership.** When a function returns a set/list/dict of results (deleted ids, affected targets, computed keys), assert full equality against the expected value. `assert x in result` / `assert expected.issubset(result)` pass even when the result grows or shrinks incorrectly. If the result is deterministic, `assert result == {…}` (or exact set equality) catches both missing and extra items.
- **Don't stop at non-emptiness when a specific result is expected.** `assert result` (or `assert len(result) > 0`) is fine for an existence-only contract, but it does not verify *which* result came back — assert the specific expected value when that is part of the behavior under test. And avoid checks that don't even establish non-emptiness: `assert result != frozenset()` is `True` for an empty `list`/`dict`, so it passes when nothing was returned.
- **Assert a positive count where the number matters.** A test that only checks "no failures" can pass while measuring zero of the thing it claims to test — e.g. if a workflow/name string changes so nothing is counted. Assert that the expected count is `> 0` (or the exact number) so a silently-zero run fails.
- **Make the scenario actually hold.** A "missing row" test must not create the row; a "no second object" test must prove the count is one. Verify the setup produces the state under test.
- **Denial tests must verify nothing changed.** When asserting an operation is rejected, also reload the target and assert its state is unchanged (or that no row was created/deleted). Asserting only that an error was returned does not prove the write was actually blocked.
- **Assert persistence from storage, not from the layer the code wrote.** When the contract is that state reaches (or is restored in) the database, reload it from the DB (e.g. `Branch.get_by_name` and check `active_schema_hash`) instead of reading back the in-memory registry/cache the code under test updated — that assertion is self-confirming and cannot detect a failure to persist.
- **Pin literal expected values — don't derive them with the code's own dependencies.** Computing the expectation with the same serializer/formatter the implementation calls (`ujson.dumps`, `yaml.dump`, the function under test itself) makes the assertion a tautology: it passes even when the library's output changes. Write the raw expected string into the test.
- **A "does not raise" test still needs an assertion.** When the contract is that an exception is swallowed, also assert a side effect that only the guarded path produces (state set before the raiser was called). With no assertion, a regression that returns early before the guard passes identically.

## Graph integrity assertions

Tests that write to the graph — migrations, merges, deletes, rebases — should assert that the graph is
still structurally sound afterwards. `infrahub.database.validation` exposes a single entry point for that:

```python
from infrahub.database.validation import collect_graph_violations, verify_graph

await verify_graph(db=db)                      # raises GraphValidationError listing every violation found
await verify_graph(db=db, kinds=["TestCar"])   # only vertices carrying one of these labels
```

It runs every graph-integrity check (duplicate paths, duplicate relationships, duplicate attributes, edges
added after a node delete, orphaned active edges under a deleted parent, relationship edge counts) and
reports all violations together rather than stopping at the first failing check. Do not call the individual
checks — a suite that picks a subset silently stops covering the rest.

Use `kinds` to scope large-graph runs to the kinds a suite actually touches. Checks anchored on an
`Attribute` or `Relationship` vertex resolve the label through the `Node` the vertex hangs off.

When a test asserts that a damaged state *exists* (a migration's "before" state, for example), use
`collect_graph_violations(...)`, which returns the violations instead of raising, and assert on the exact
checks reported.

## See Also

- [Python Standards](python.md) - General Python coding standards
- [Backend Architecture](../../knowledge/backend/architecture.md) - Backend architecture overview
